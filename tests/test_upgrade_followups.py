"""Upgrade follow-ups stay visible until source data actually satisfies them."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import indexx_search as search
import indexx_upgrade as upgrade


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="indexx-upgrade-test-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "library with spaces"
        self.root.mkdir()
        self.rows = []
        self.write(".indexx.json", json.dumps({"paths": {
            "use_catalog": "catalog", "instagram_catalog": "catalog/saves.md"}}))
        self.catalog()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def source(self, item_id, **fields):
        front = dict(id=item_id, platform="instagram", handle="creator", **fields)
        return self.write(f"wiki/sources/instagram/{item_id}.md", self.document(front))

    def document(self, front, body="# Story\n\nA supported summary of the retained evidence."):
        return "---\n" + "\n".join(f"{key}: {json.dumps(value)}" for key, value in front.items()) + "\n---\n" + body

    def item(self, item_id, status="wiki_ingested", source=True, **fields):
        self.rows.append([item_id, f"https://www.instagram.com/p/{item_id}/", "image", status, ""])
        if source:
            self.source(item_id, **fields)
        self.catalog()

    def catalog(self):
        self.write("catalog/saves.md", "| shortcode | url | type | status | media_path |\n"
                   "| --- | --- | --- | --- | --- |\n"
                   + "".join("| " + " | ".join(row) + " |\n" for row in self.rows))

    def check(self, result, check_id="existing-story-people-v1"):
        return next(check for check in result["checks"] if check["id"] == check_id)

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                if path.is_file() else None for path in self.root.rglob("*")}

    def test_existing_stories_are_separate_from_unprocessed_backlog(self):
        for i in range(16):
            self.item(f"Story{i}")
        for i in range(888):
            self.rows.append([f"Pending{i}", f"https://www.instagram.com/p/Pending{i}/", "image", "discovered", ""])
        self.catalog()
        search.build_index(self.root)
        result = upgrade.report(self.root)
        self.assertEqual(result["scope"], {"catalog_total": 904, "claimed_complete_stories": 16,
                                        "unprocessed_backlog": 888, "terminal_excluded": 0})
        people = self.check(result)
        self.assertEqual(people["pending_count"], 16)
        self.assertEqual(people["pending_ids"], [f"Story{i}" for i in range(16)])
        self.assertEqual(people["blocked_count"], 0)
        self.assertTrue(self.check(result, "local-search-v1")["index"]["fresh"])
        self.assertEqual(result["status"], "attention")

    def test_valid_empty_review_and_evidenced_people_are_complete(self):
        self.write("wiki/entities/people/example-person.md", self.document(
            {"id": "example-person", "name": "Example Person", "aliases": []},
            "# Person\n\nCaption attribution: [[sources/instagram/Known]]"))
        annotation = {"id": "example-person", "name": "Example Person", "role": "speaker",
                      "evidence": "The retained caption explicitly credits Example Person as the speaker."}
        self.item("Known", people=[annotation], people_reviewed=True)
        self.item("Unknown", people=[], people_reviewed=True)
        self.item("NotFinished", people=[], people_reviewed=False)
        result = upgrade.report(self.root)
        self.assertEqual(self.check(result)["reviewed_count"], 2)
        self.assertEqual(self.check(result)["pending_ids"], ["NotFinished"])
        self.source("NotFinished", people=[], people_reviewed=True)
        search.build_index(self.root)
        result = upgrade.report(self.root)
        self.assertEqual(result["status"], "ready")
        self.assertIsNone(result["suggested_reply"])
        self.assertTrue(all(item["people_reviewed"] for item in search.search(self.root, limit=None)["results"]))

    def test_install_revision_does_not_hide_deferred_work(self):
        self.item("OlderStory")
        search.build_index(self.root)
        before = upgrade.report(self.root)
        self.write("logs/install.json", json.dumps({"revision": "b" * 40, "status": "installed"}))
        self.assertEqual(upgrade.report(self.root), before)
        self.assertEqual(upgrade.report(self.root)["suggested_reply"], "Refresh existing stories")

    def test_flag_alone_or_invalid_annotations_do_not_count_as_reviewed(self):
        self.item("FlagOnly", people_reviewed=True)
        self.item("BadFlag", people=[], people_reviewed="true")
        self.item("MissingPerson", people=[{"id": "missing-person", "name": "Missing Person",
                  "role": "speaker", "evidence": "An explicit caption credit."}], people_reviewed=True)
        people = self.check(upgrade.report(self.root))
        self.assertEqual(people["reviewed_count"], 0)
        self.assertEqual(people["pending_ids"], ["FlagOnly", "BadFlag", "MissingPerson"])
        self.assertEqual(self.check(upgrade.report(self.root), "search-inputs-v1")["warning_count"], 3)

    def test_missing_malformed_and_wrong_identity_sources_are_blocked(self):
        self.item("Missing", source=False)
        self.item("Malformed")
        self.write("wiki/sources/instagram/Malformed.md", "---\npeople:\n  - bad yaml\n---\nBody")
        self.item("WrongIdentity")
        self.write("wiki/sources/instagram/WrongIdentity.md", self.document({"id": "Other", "platform": "instagram"}))
        people = self.check(upgrade.report(self.root))
        self.assertEqual(people["blocked_ids"], ["Missing", "Malformed", "WrongIdentity"])
        self.assertEqual(people["pending_count"], 0)
        self.assertEqual(people["status"], "attention")

    def test_fresh_index_with_creator_warnings_is_still_actionable(self):
        self.item("Reviewed", people=[], people_reviewed=True)
        self.write("wiki/entities/creators/creator.md", "---\naliases:\n  - legacy yaml\n---\n# Creator\n\nOriginal cited prose.")
        search.build_index(self.root)
        before = self.snapshot()
        result = upgrade.report(self.root)
        self.assertEqual(result["status"], "attention")
        self.assertEqual(self.check(result)["status"], "ready")
        self.assertTrue(self.check(result, "local-search-v1")["index"]["fresh"])
        warnings = self.check(result, "search-inputs-v1")
        self.assertEqual(warnings["warning_count"], 1)
        self.assertIn("wiki/entities/creators/creator.md:", warnings["warnings"][0])
        self.assertEqual(self.snapshot(), before)

    def test_creator_without_frontmatter_does_not_need_a_spurious_repair(self):
        self.item("Reviewed", people=[], people_reviewed=True)
        self.write("wiki/entities/creators/creator.md", "# Creator\n\n[[sources/instagram/Reviewed]]")
        search.build_index(self.root)
        self.assertEqual(upgrade.report(self.root)["status"], "ready")

    def test_missing_and_stale_index_checks_do_not_build(self):
        self.item("Old")
        before = self.snapshot()
        self.assertFalse(self.check(upgrade.report(self.root), "local-search-v1")["index"]["fresh"])
        self.assertEqual(self.snapshot(), before)
        search.build_index(self.root)
        self.source("Old", people=[], people_reviewed=True)
        before = self.snapshot()
        result = upgrade.report(self.root)
        self.assertFalse(self.check(result, "local-search-v1")["index"]["fresh"])
        self.assertEqual(self.check(result)["reviewed_count"], 1)
        self.assertEqual(self.snapshot(), before)

    def test_excluded_and_unfinished_items_are_not_refresh_candidates(self):
        for state in ("discovered", "metadata", "downloaded", "transcribed", "partial", "unavailable", "skipped_no_video"):
            self.item(state.replace("_", ""), status=state, people=[], people_reviewed=True)
        result = upgrade.report(self.root)
        self.assertEqual(result["scope"]["unprocessed_backlog"], 5)
        self.assertEqual(result["scope"]["terminal_excluded"], 2)
        self.assertEqual(self.check(result)["eligible_count"], 0)

    def test_legacy_catalog_selection(self):
        self.item("Old")
        self.write(".indexx.json", json.dumps({"paths": {
            "use_catalog": "legacy", "instagram_catalog_legacy": "catalog/saves.md",
            "instagram_catalog": "absent.md"}}))
        self.assertEqual(self.check(upgrade.report(self.root))["pending_ids"], ["Old"])

    def test_input_change_cannot_report_readiness(self):
        with patch.object(search, "_current_manifest", return_value={"changed": True}):
            with self.assertRaisesRegex(ValueError, "changed during checking"):
                upgrade.report(self.root)

    def test_unrecognized_cache_is_reported_without_overwriting(self):
        self.write(search.CACHE, "not a search database")
        before = self.snapshot()
        result = upgrade.report(self.root)
        self.assertEqual(result["status"], "attention")
        self.assertFalse(self.check(result, "local-search-v1")["index"]["fresh"])
        self.assertEqual(self.snapshot(), before)

    def test_cli_never_writes_even_import_caches_and_reports_bad_catalog(self):
        for name in ("indexx_upgrade.py", "indexx_search.py", "indexx_status.py"):
            target = self.root / "scripts" / name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(SCRIPTS / name, target)
        self.item("Old")
        command = [sys.executable, str(self.root / "scripts/indexx_upgrade.py"), "--root", str(self.root)]
        for invalid in (False, True):
            if invalid:
                self.write("catalog/saves.md", "broken table")
            before = self.snapshot()
            result = subprocess.run(command, cwd=self.root.parent, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1 if invalid else 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "blocked" if invalid else "attention")
            self.assertEqual(self.snapshot(), before)

    def test_source_symlink_escape_is_reported_without_reading_target(self):
        self.item("Linked", source=False)
        outside = self.root.parent / "outside.md"
        outside.write_text(self.document({"id": "Linked", "platform": "instagram", "people_reviewed": True, "people": []}))
        target = self.root / "wiki/sources/instagram/Linked.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        original = Path.read_bytes
        def safe_read(path):
            if path.resolve() == outside:
                raise AssertionError("Read a source outside the library")
            return original(path)
        with patch.object(Path, "read_bytes", safe_read):
            result = upgrade.report(self.root)
        self.assertEqual(self.check(result)["blocked_ids"], ["Linked"])
        self.assertTrue(self.check(result, "search-inputs-v1")["warnings"])

    def test_check_reads_metadata_but_never_media_bytes(self):
        self.item("Video")
        folder = "media/instagram/creator/Video"
        self.rows[0][2] = "reel"
        self.rows[0][4] = folder
        self.catalog()
        self.write(folder + "/info.json", json.dumps({"id": "Video", "platform": "instagram",
            "handle": "creator", "type": "video", "source_url": self.rows[0][1]}))
        media = self.write(folder + "/media.mp4", "Do not read this fixture")
        original = Path.read_bytes
        def safe_read(path):
            if path == media:
                raise AssertionError("Read media bytes during a feature check")
            return original(path)
        with patch.object(Path, "read_bytes", safe_read):
            self.assertEqual(self.check(upgrade.report(self.root))["pending_ids"], ["Video"])


if __name__ == "__main__":
    unittest.main()
