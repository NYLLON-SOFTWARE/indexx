"""Regression coverage for the public/private export boundary."""

import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "scripts"))
import indexx_export


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "docs").mkdir()
        shutil.copyfile(REPOSITORY / indexx_export.MANIFEST_PATH,
                        self.root / indexx_export.MANIFEST_PATH)
        shutil.copytree(REPOSITORY / "skills", self.root / "skills")

    def manifest(self):
        return json.loads((self.root / indexx_export.MANIFEST_PATH).read_text())

    def write_manifest(self, manifest):
        (self.root / indexx_export.MANIFEST_PATH).write_text(json.dumps(manifest))

    def run_export(self, *arguments):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return indexx_export.main(["--root", str(self.root), *arguments])

    def test_all_eleven_skill_bodies_and_descriptions_match_sources(self):
        payload = indexx_export.build_payload(self.root)
        self.assertEqual(len(payload["skills"]), 11)
        self.assertEqual([skill["name"] for skill in payload["skills"]],
                         list(indexx_export.PUBLIC_SKILLS))
        for skill in payload["skills"]:
            source = (self.root / "skills" / skill["name"] / "SKILL.md").read_text()
            header, expected_body = source[4:].split("\n---\n", 1)
            description_lines = header.split("description: >-\n", 1)[1].splitlines()
            expected_description = " ".join(line.strip() for line in description_lines)
            self.assertEqual(skill["content"], expected_body.strip())
            self.assertEqual(skill["description"], expected_description)

    def test_generation_is_deterministic_and_check_detects_source_drift(self):
        self.assertEqual(self.run_export(), 0)
        first = (self.root / indexx_export.OUTPUT_PATH).read_bytes()
        self.assertEqual(self.run_export(), 0)
        self.assertEqual((self.root / indexx_export.OUTPUT_PATH).read_bytes(), first)
        self.assertEqual(self.run_export("--check"), 0)
        source = self.root / "skills/indexx-setup/SKILL.md"
        source.write_text(source.read_text() + "\nNew setup instruction.\n")
        self.assertEqual(self.run_export("--check"), 1)
        self.assertEqual((self.root / indexx_export.OUTPUT_PATH).read_bytes(), first)

    def test_check_rejects_hand_edited_bundle(self):
        self.assertEqual(self.run_export(), 0)
        output = self.root / indexx_export.OUTPUT_PATH
        payload = json.loads(output.read_text())
        payload["memory"] = [{"content": "A private library locator"}]
        output.write_text(json.dumps(payload))
        self.assertEqual(self.run_export("--check"), 1)

    def test_private_runtime_files_do_not_influence_export(self):
        expected = indexx_export.render_payload(self.root)
        private_files = (
            ".indexx.json", "memory.json", "catalog/saves-index.md",
            "media/instagram/private/info.json", "logs/pipeline-progress.md",
            "logs/jobs/private.json", "wiki/index.md", ".env",
        )
        for relative in private_files:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"PRIVATE_RUNTIME_SENTINEL\xff\x00")
        actual = indexx_export.render_payload(self.root)
        self.assertEqual(actual, expected)
        self.assertNotIn("PRIVATE_RUNTIME_SENTINEL", actual)
        self.assertEqual(json.loads(actual)["memory"], [])

    def test_rejects_unknown_and_personal_manifest_fields(self):
        original = self.manifest()
        for field in ("libraryRoot", "configuration", "accounts", "liveMemory", "jobApproval"):
            with self.subTest(field=field):
                manifest = dict(original)
                manifest[field] = "private value"
                self.write_manifest(manifest)
                with self.assertRaisesRegex(ValueError, "exactly"):
                    indexx_export.build_payload(self.root)
        original["profile"]["libraryRoot"] = "/private/library"
        self.write_manifest(original)
        with self.assertRaisesRegex(ValueError, "exactly"):
            indexx_export.build_payload(self.root)

    def test_rejects_live_memories_routines_and_connections(self):
        original = self.manifest()
        for field in ("memory", "routines", "plugins"):
            with self.subTest(field=field):
                manifest = dict(original)
                manifest[field] = [{"content": "private runtime state"}]
                self.write_manifest(manifest)
                with self.assertRaisesRegex(ValueError, "must be empty"):
                    indexx_export.build_payload(self.root)

    def test_rejects_unreviewed_or_missing_skill(self):
        extra = self.root / "skills/new-unreviewed/SKILL.md"
        extra.parent.mkdir()
        extra.write_text("---\nname: Private\ndescription: Private\n---\nPrivate content.")
        with self.assertRaisesRegex(ValueError, "unreviewed=.*new-unreviewed"):
            indexx_export.build_payload(self.root)
        extra.unlink()
        (self.root / "skills/indexx-setup/SKILL.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing=.*indexx-setup"):
            indexx_export.build_payload(self.root)

    def test_manifest_cannot_select_runtime_paths(self):
        manifest = self.manifest()
        manifest["skills"][0] = "../../.indexx.json"
        self.write_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "allowlist"):
            indexx_export.build_payload(self.root)

    def test_symlink_cannot_redirect_skill_to_private_data(self):
        private = self.root / "private-state"
        private.write_text("PRIVATE_RUNTIME_SENTINEL")
        source = self.root / "skills/indexx-setup/SKILL.md"
        source.unlink()
        source.symlink_to(private)
        with self.assertRaisesRegex(ValueError, "symlink"):
            indexx_export.build_payload(self.root)


if __name__ == "__main__":
    unittest.main()
