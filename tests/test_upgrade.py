"""Exercise the reported legacy upgrade across migration, installation, and audit."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load("upgrade_installer", "indexx_install.py")
migration = load("upgrade_migration", "indexx_migrate.py")
status = load("upgrade_status", "indexx_status.py")


class LegacyUpgradeIntegrationTests(unittest.TestCase):
    def test_reported_library_can_upgrade_without_losing_rows_or_hiding_failed_claims(self):
        with tempfile.TemporaryDirectory(prefix="indexx-upgrade-test-") as temporary:
            root = Path(temporary) / "library"
            root.mkdir()
            config = json.loads((REPO / "examples/.indexx.example.json").read_text())
            config.update(root=str(root), private_note="preserve my preferences")
            config["batch"]["download_n"] = 3
            config["stt"] = {"primary": "elevenlabs_scribe_v2"}
            config_path = root / ".indexx.json"
            config_path.write_text(json.dumps(config))
            catalog = root / config["paths"]["instagram_catalog_legacy"]
            catalog.parent.mkdir(parents=True)
            cursor = '---\ncount: 904\nwatermark_shortcodes: ["Done0"]\nlast_clean_stop: true\n---\n\n'
            rows = [(f"Done{i}", "wiki_ingested") for i in range(16)]
            rows += [(f"Backlog{i}", "active") for i in range(888)]
            text = cursor + "| shortcode | url | type | status | note |\n| --- | --- | --- | --- | --- |\n"
            text += "".join(f"| {item_id} | https://www.instagram.com/reel/{item_id}/ | reel | {stage} | keep \\| note |\n" for item_id, stage in rows)
            catalog.write_text(text)
            original_support = {}
            for relative in installer.SUPPORT_PATHS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                original_support[relative] = f"older unmanaged {relative}\n".encode()
                path.write_bytes(original_support[relative])
            manifest = root / "logs/install.json"
            manifest.parent.mkdir()
            # The earlier installer could record an attempted revision without hashes.
            manifest.write_text(json.dumps({"source_revision": "a" * 40, "files": {}}))
            for item_id, _ in rows[:16]:
                folder = root / "media/instagram/creator" / item_id
                folder.mkdir(parents=True)
                (folder / "info.json").write_text(json.dumps({
                    "id": item_id, "platform": "instagram", "handle": "creator",
                    "source_url": f"https://www.instagram.com/reel/{item_id}/",
                    "type": "video", "transcript_status": "speech",
                }))
                (folder / "media.mp4").write_bytes(b"existing media bytes")
                (folder / "transcript.md").write_text("Existing transcript must remain unchanged.\n")

            def snapshot():
                return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

            before = snapshot()
            revision = "b" * 40
            preview = installer.plan(REPO, root, revision, refresh=True)
            self.assertEqual(preview["status"], "blocked")
            self.assertEqual(set(preview["conflicts"]), set(installer.SUPPORT_PATHS))
            self.assertTrue(preview["migration_required"])
            blocked = installer.install(REPO, root, revision, refresh=True)
            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(snapshot(), before)

            migration_preview = migration.plan_migration(root, provider="elevenlabs")
            self.assertEqual(migration_preview["rows"], 904)
            self.assertEqual(snapshot(), before)
            migrated = migration.apply_migration(root, provider="elevenlabs")
            self.assertEqual(migrated["artifact_audit"], "not_run")
            backup_files = migrated["backup_files"]
            self.assertEqual(Path(backup_files[catalog.relative_to(root).as_posix()]).read_bytes(), before[catalog.relative_to(root).as_posix()])
            self.assertEqual(Path(backup_files[".indexx.json"]).read_bytes(), before[".indexx.json"])
            converted = status.parse_catalog(catalog.read_text())
            self.assertEqual([r["shortcode"] for r in converted], [r[0] for r in rows])
            self.assertTrue(catalog.read_text().startswith(cursor))
            self.assertTrue(all(r["note"] == "keep | note" for r in converted))
            self.assertTrue(all(r["status"] == "wiki_ingested" for r in converted[:16]))
            self.assertTrue(all(r["status"] == "discovered" and r["legacy_status"] == "active" for r in converted[16:]))
            self.assertTrue(all(not r["media_path"] for r in converted[16:]))
            self.assertEqual(migration.apply_migration(root)["mode"], "no_changes")

            # Data migration does not silently authorize replacing local support.
            self.assertEqual(installer.plan(REPO, root, revision, refresh=True)["status"], "blocked")
            self.assertEqual(manifest.read_bytes(), before["logs/install.json"])
            installed = installer.install(REPO, root, revision, refresh=True, replace_support=installer.SUPPORT_PATHS)
            self.assertEqual(installed["status"], "installed")
            self.assertEqual(installed["artifact_audit"], "not_run")
            self.assertEqual(json.loads(manifest.read_text())["source_revision"], revision)
            support_backup = root / installed["backup_path"]
            for relative, original in original_support.items():
                self.assertEqual((support_backup / relative).read_bytes(), original)
                self.assertEqual((root / relative).read_bytes(), (REPO / relative).read_bytes())
            final_config = json.loads(config_path.read_text())
            self.assertEqual(final_config["stt"]["provider"], "elevenlabs")
            self.assertEqual(final_config["batch"]["download_n"], 3)
            self.assertEqual(final_config["private_note"], config["private_note"])
            for relative, content in before.items():
                if relative.startswith("media/"):
                    self.assertEqual((root / relative).read_bytes(), content)

            audit = subprocess.run([sys.executable, str(root / "scripts/indexx_status.py"), "--root", str(root), "--json"], capture_output=True, text=True)
            self.assertNotEqual(audit.returncode, 0)
            report = json.loads(audit.stdout)
            self.assertEqual(report["total"], 904)
            self.assertEqual(report["claimed_complete"], 16)
            self.assertEqual(report["fully_processed"], 0)
            self.assertEqual(report["invalid_complete"], 16)
            self.assertEqual(report["backlog"], 888)


if __name__ == "__main__":
    unittest.main()
