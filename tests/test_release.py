import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "scripts/build_release.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ReleaseTests(unittest.TestCase):
    def test_packages_are_self_contained_and_exclude_private_data(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            source = workspace / "source"
            shutil.copytree(ROOT / "skills", source / "skills")
            shutil.copytree(ROOT / ".codex-plugin", source / ".codex-plugin")
            for filename in ["plugin.json", "README.md", "LICENSE"]:
                if (ROOT / filename).exists():
                    shutil.copy2(ROOT / filename, source / filename)
            (source / "skills/instagram-saved-ids/private-capture.jsonl").write_text("PRIVATE_SENTINEL")
            (source / "skills/instagram-saved-ids/scripts/credentials.txt").write_text("PRIVATE_SENTINEL")
            archives = builder.build(source, workspace / "dist")
            first_bytes = [path.read_bytes() for path in archives]
            builder.build(source, workspace / "dist")
            self.assertEqual(first_bytes, [path.read_bytes() for path in archives])

            for archive_path in archives:
                with ZipFile(archive_path) as archive:
                    for name in archive.namelist():
                        self.assertNotIn(b"PRIVATE_SENTINEL", archive.read(name))
                        self.assertFalse(name.endswith(".jsonl"))
                        self.assertFalse(name.endswith(".py"))
                    target = workspace / archive_path.stem
                    archive.extractall(target)
                skill = target / "instagram-saved-ids"
                if not skill.exists():
                    skill = target / "skills/instagram-saved-ids"
                for relative in builder.SKILL_FILES:
                    self.assertTrue((skill / relative).is_file(), relative)
                run = subprocess.run([
                    "node", "-e",
                    "const fs = require('node:fs'), vm = require('node:vm'); "
                    "const context = vm.createContext({ URL }); "
                    "vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context); "
                    "const batches = fs.readFileSync(process.argv[2], 'utf8').trim().split(/\\r?\\n/).map(JSON.parse); "
                    "console.log(JSON.stringify(context.normalizeSavedItems(batches, {reason: 'Synthetic packaged smoke test'}).result));",
                    str(skill / "scripts/export_ids.js"), str(ROOT / "examples/checkpoints.jsonl"),
                ], capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(run.stdout)["unique_count"], 3)


if __name__ == "__main__":
    unittest.main()
