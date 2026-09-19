"""Regression checks for stage-gate updates, migration and interrupted writes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "indexx_progress.py"
spec = importlib.util.spec_from_file_location("indexx_progress", SCRIPT)
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.board = self.root / "logs" / "pipeline-progress.md"
        self.sidecar = self.root / "logs" / "pipeline-progress.json"

    def run_cli(self, *args, okay=True):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                                text=True, capture_output=True, env={**os.environ, "TZ": "UTC"})
        self.assertEqual(result.returncode == 0, okay, result.stderr)
        return result

    def state(self):
        return json.loads(self.sidecar.read_text())

    def test_upsert_preserves_rows_fields_order_and_title(self):
        self.run_cli("--title", "Saved batch", "--row", 'id=A handle=alice dl=done note="Downloaded clip"')
        self.run_cli("--row", "id=B handle=bob watch=running")
        self.run_cli("--row", "id=A stt=done")
        state = self.state()
        self.assertEqual(state["title"], "Saved batch")
        self.assertEqual([row["id"] for row in state["rows"]], ["A", "B"])
        self.assertEqual(state["rows"][0], {"id": "A", "handle": "alice", "dl": "done",
                                             "note": "Downloaded clip", "stt": "done"})
        self.assertEqual(state["rows"][1]["watch"], "running")
        self.assertTrue(state["updated_at"].endswith("+00:00"))

    def test_clear_resets_only_when_requested(self):
        self.run_cli("--title", "Old batch", "--row", "id=A dl=done")
        self.run_cli("--clear", "--row", "id=B watch=skip")
        self.assertEqual(self.state()["title"], "INDEXX batch")
        self.assertEqual(self.state()["rows"], [{"id": "B", "watch": "skip"}])
        self.assertNotIn("| A |", self.board.read_text())

    def test_quoted_notes_and_markdown_are_preserved_safely(self):
        note = 'Check a|b and [link](https://example.com) <script>\nsecond line'
        self.run_cli("--row", f'id=A note="{note}"')
        self.assertEqual(self.state()["rows"][0]["note"], note)
        board = self.board.read_text()
        self.assertIn(r"a\|b", board)
        self.assertIn(r"\[link\]\(https://example.com\)", board)
        self.assertIn("&lt;script&gt;<br>second line", board)
        self.assertEqual(len([line for line in board.splitlines() if line.startswith("| A |")]), 1)

    def test_invalid_updates_do_not_change_existing_files(self):
        self.run_cli("--row", "id=A dl=done")
        before = (self.sidecar.read_bytes(), self.board.read_bytes())
        for row in ["note=no-id", "id=A stt=unknown", "id=A note=two words", "id=A id=B", "id=A surprise=yes"]:
            with self.subTest(row=row):
                self.run_cli("--row", row, okay=False)
                self.assertEqual((self.sidecar.read_bytes(), self.board.read_bytes()), before)

    def test_migrates_legacy_board_before_updating(self):
        self.board.parent.mkdir()
        self.board.write_text(
            "# Existing batch\n\n_Updated 2026-09-19 10:00 PDT_\n\n"
            "| id | handle | dl | aud | watch | stt | tags | wiki | note |\n"
            "|----|--------|---|---|---|---|---|---|------|\n"
            "| A | alice | ✓ | ✓ | ✗ | ○ | ○ | ○ | Old note |\n"
        )
        self.run_cli("--row", "id=B dl=running", "--row", "id=A stt=done")
        state = self.state()
        self.assertEqual(state["title"], "Existing batch")
        self.assertEqual([row["id"] for row in state["rows"]], ["A", "B"])
        self.assertEqual(state["rows"][0]["dl"], "done")
        self.assertEqual(state["rows"][0]["watch"], "fail")
        self.assertEqual(state["rows"][0]["note"], "Old note")

    def test_corrupt_state_is_preserved_until_explicit_clear(self):
        self.run_cli("--row", "id=A dl=done")
        self.sidecar.write_text("{broken")
        old_board = self.board.read_bytes()
        self.run_cli("--row", "id=B dl=done", okay=False)
        self.assertEqual(self.sidecar.read_text(), "{broken")
        self.assertEqual(self.board.read_bytes(), old_board)
        self.run_cli("--clear")
        self.assertEqual(self.state()["rows"], [])

    def test_state_rebuilds_missing_markdown_without_losing_progress(self):
        self.run_cli("--title", "Keep me", "--row", "id=A wiki=done")
        self.board.unlink()
        self.run_cli()
        self.assertIn("# Keep me", self.board.read_text())
        self.assertEqual(self.state()["rows"], [{"id": "A", "wiki": "done"}])

    def test_failed_atomic_replace_preserves_original_and_cleans_temp(self):
        target = self.root / "state.json"
        target.write_text("original")
        with patch.object(progress.os, "replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                progress.atomic_write(target, "replacement")
        self.assertEqual(target.read_text(), "original")
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_logs_symlink_cannot_escape_root_even_with_clear(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside)
            private = external / "pipeline-progress.json"
            private.write_text("outside content must not be read or changed")
            self.board.parent.symlink_to(external, target_is_directory=True)
            for flags in [(), ("--clear",)]:
                with self.subTest(flags=flags):
                    result = self.run_cli(*flags, "--row", "id=A dl=done", okay=False)
                    self.assertIn("outside the library", result.stderr)
                    self.assertEqual(private.read_text(), "outside content must not be read or changed")
                    self.assertEqual(list(external.iterdir()), [private])
                    self.assertTrue(self.board.parent.is_symlink())

    def test_output_symlinks_cannot_escape_root_or_be_replaced_by_clear(self):
        self.board.parent.mkdir()
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "private.txt"
            for path in [self.sidecar, self.board]:
                for exists in [False, True]:
                    with self.subTest(path=path.name, exists=exists):
                        if exists:
                            external.write_text("private")
                        path.symlink_to(external)
                        for flags in [(), ("--clear",)]:
                            result = self.run_cli(*flags, "--row", "id=A dl=done", okay=False)
                            self.assertIn("outside the library", result.stderr)
                            self.assertTrue(path.is_symlink())
                            self.assertEqual(list(self.board.parent.iterdir()), [path])
                            self.assertEqual(external.exists(), exists)
                            if exists:
                                self.assertEqual(external.read_text(), "private")
                        path.unlink()
                        external.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
