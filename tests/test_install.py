import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("indexx_install", REPO / "scripts/indexx_install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
REVISION = "a" * 40


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="indexx-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.root = self.base / "personal library"
        self.source.mkdir()
        for name in installer.SUPPORT:
            (self.source / name).write_text("support v1\n")
        (self.source / "scripts").mkdir()
        for name in installer.RUNTIME_SCRIPTS:
            (self.source / "scripts" / name).write_text("# helper v1\n")
        (self.source / "templates/wiki/taxonomies").mkdir(parents=True)
        (self.source / "templates/wiki/index.md").write_text("# Library\n")
        (self.source / "templates/wiki/taxonomies/tags.md").write_text("# Tags\n")
        (self.source / "examples").mkdir()
        shutil.copyfile(REPO / "examples/.indexx.example.json", self.source / "examples/.indexx.example.json")
        shutil.copyfile(REPO / "examples/saves-index.example.md", self.source / "examples/saves-index.example.md")

    def run_install(self, **kwargs):
        return installer.install(self.source, self.root, REVISION, **kwargs)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() if p.is_file() else None
                for p in self.root.rglob("*")}

    def test_new_install_copies_support_and_starts_without_provider(self):
        result = self.run_install()
        config = json.loads((self.root / ".indexx.json").read_text())
        self.assertEqual(config["root"], str(self.root.resolve()))
        self.assertIsNone(config["stt"]["provider"])
        self.assertEqual(config["batch"]["download_n"], 10)
        self.assertTrue((self.root / "scripts/indexx_status.py").is_file())
        self.assertTrue((self.root / "wiki/taxonomies/tags.md").is_file())
        self.assertTrue((self.root / "markdown/instagram/saves-index.md").is_file())
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["status"], "installed")
        self.assertEqual(result["artifact_audit"], "not_run")

    def test_fresh_plan_is_read_only_and_json_serializable(self):
        result = installer.plan(self.source, self.root, REVISION)
        self.assertEqual(result["status"], "ready")
        self.assertIn("AGENTS.md", result["planned"]["create"])
        json.dumps(result)
        self.assertFalse(self.root.exists())

    def test_real_support_bundle_audits_and_renders_a_fresh_library(self):
        # File-install integration only: no media tools, connector auth, or API calls.
        installer.install(REPO, self.root, REVISION)
        audit = subprocess.run(
            [sys.executable, str(self.root / "scripts/indexx_status.py"), "--root", str(self.root), "--json"],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(json.loads(audit.stdout)["total"], 0)
        subprocess.run(
            [sys.executable, str(self.root / "scripts/indexx_dashboard.py"), "--root", str(self.root)],
            check=True, capture_output=True, text=True,
        )
        self.assertTrue((self.root / "logs/dashboard.html").is_file())

    def test_repair_preserves_choices_and_all_user_content(self):
        self.run_install()
        config_path = self.root / ".indexx.json"
        config = json.loads(config_path.read_text())
        config["stt"]["provider"] = "elevenlabs"
        config["batch"]["download_n"] = 3
        config["paths"]["use_catalog"] = "catalog"
        del config["batch"]["wiki_n"]
        config_path.write_text(json.dumps(config))
        custom = {
            "catalog/instagram-saves.md": (self.source / "examples/saves-index.example.md").read_text() + "\nMy catalog notes\n",
            "wiki/taxonomies/tags.md": "my tags",
            "wiki/index.md": "my wiki",
            "media/instagram/creator/item/transcript.md": "my transcript",
        }
        for name, value in custom.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        (self.root / "scripts/indexx_status.py").unlink()
        result = self.run_install()
        self.assertEqual(result["status"], "installed")
        after = json.loads(config_path.read_text())
        self.assertEqual(after["stt"]["provider"], "elevenlabs")
        self.assertEqual(after["batch"]["download_n"], 3)
        self.assertEqual(after["batch"]["wiki_n"], 20)
        for name, value in custom.items():
            self.assertEqual((self.root / name).read_text(), value)
        self.assertTrue((self.root / "scripts/indexx_status.py").is_file())

    def test_refresh_updates_only_unmodified_managed_support(self):
        self.run_install()
        (self.source / "AGENTS.md").write_text("new official instructions")
        (self.source / "scripts/indexx_progress.py").write_text("# helper v2")
        result = self.run_install(refresh=True)
        self.assertEqual(result["conflicts"], [])
        self.assertEqual((self.root / "AGENTS.md").read_text(), "new official instructions")
        self.assertIn("scripts/indexx_progress.py", result["updated"])
        self.assertEqual((self.root / "scripts/indexx_progress.py").read_text(), "# helper v2")

    def test_conflicts_block_every_write_and_manifest_revision(self):
        self.run_install()
        (self.root / "AGENTS.md").write_text("user edited instructions")
        (self.source / "scripts/indexx_progress.py").write_text("# helper v2")
        before = self.snapshot()
        for action in (installer.plan, installer.install):
            result = action(self.source, self.root, "b" * 40, refresh=True)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["conflict_details"], [{"path": "AGENTS.md", "reason": "modified-managed"}])
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(json.loads((self.root / "logs/install.json").read_text())["source_revision"], REVISION)

    def test_unmanaged_and_old_managed_files_are_classified_truthfully(self):
        self.run_install()
        manifest_path = self.root / "logs/install.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["files"]["AGENTS.md"]
        manifest_path.write_text(json.dumps(manifest))
        (self.source / "AGENTS.md").write_text("support v2")
        (self.source / "README.md").write_text("readme v2")
        before = self.snapshot()
        result = installer.plan(self.source, self.root, REVISION)
        self.assertEqual(result["conflict_details"], [
            {"path": "AGENTS.md", "reason": "unmanaged"},
            {"path": "README.md", "reason": "managed-needs-refresh"},
        ])
        self.assertEqual(self.snapshot(), before)

    def test_byte_identical_unmanaged_support_is_adopted(self):
        self.run_install()
        (self.root / "logs/install.json").unlink()
        result = self.run_install(refresh=True)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(set(result["planned"]["adopt"]), set(installer.SUPPORT_PATHS))
        manifest = json.loads((self.root / "logs/install.json").read_text())
        self.assertEqual(set(manifest["files"]), set(installer.SUPPORT_PATHS))
        for relative, checksum in manifest["files"].items():
            self.assertEqual(checksum, installer.digest((self.root / relative).read_bytes()))

    def test_explicit_replacement_is_planned_then_backed_up_before_update(self):
        self.run_install()
        custom = {"AGENTS.md": b"my instructions", "scripts/indexx_progress.py": b"# personal helper"}
        for name, value in custom.items():
            (self.root / name).write_bytes(value)
        before = self.snapshot()
        result = installer.plan(self.source, self.root, "b" * 40, replace_support=tuple(custom))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(set(result["planned"]["replace"]), set(custom))
        self.assertEqual(self.snapshot(), before)
        original_write = installer.atomic_write
        def verify_backups(path, data):
            if str(path.relative_to(self.root.resolve())) in custom:
                for name, value in custom.items():
                    backups = list((self.root / "logs/install-backups").glob(f"*/{name}"))
                    self.assertEqual(len(backups), 1)
                    self.assertEqual(backups[0].read_bytes(), value)
            original_write(path, data)
        with mock.patch.object(installer, "atomic_write", side_effect=verify_backups):
            result = installer.install(self.source, self.root, "b" * 40, replace_support=tuple(custom))
        self.assertEqual(result["status"], "installed")
        self.assertEqual(set(result["replaced"]), set(custom))
        for name, value in custom.items():
            self.assertEqual((self.root / result["backup_path"] / name).read_bytes(), value)
            self.assertEqual((self.root / name).read_bytes(), (self.source / name).read_bytes())
        manifest = json.loads((self.root / "logs/install.json").read_text())
        self.assertEqual(manifest["source_revision"], "b" * 40)

    def test_replacement_permission_does_not_bypass_catalog_blocker(self):
        self.run_install()
        (self.root / "AGENTS.md").write_text("personal")
        (self.root / "markdown/instagram/saves-index.md").write_text("| shortcode | status |\n|---|---|\n| abc | active |\n")
        before = self.snapshot()
        result = self.run_install(replace_support=("AGENTS.md",))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("media_path", result["migration_required"][0])
        self.assertEqual(self.snapshot(), before)

    def test_legacy_catalog_and_provider_block_checks_and_installs_without_writes(self):
        self.run_install()
        catalog = self.root / "markdown/instagram/saves-index.md"
        config_path = self.root / ".indexx.json"
        current_config = json.loads(config_path.read_text())
        for catalog_text in (
            "| shortcode | status |\n|---|---|\n| abc | active |\n",
            "| shortcode | url | type | status | media_path |\n|---|---|---|---|---|\n| abc | https://instagram.com/p/abc/ | reel | active | |\n",
            "not a catalog",
        ):
            for stt in ({"provider": "elevenlabs_scribe_v2"}, {"primary": "grok", "fallback": "elevenlabs"}):
                with self.subTest(catalog=catalog_text, stt=stt):
                    catalog.write_text(catalog_text)
                    config_path.write_text(json.dumps(dict(current_config, stt=stt)))
                    before = self.snapshot()
                    for action in (installer.plan, installer.install):
                        result = action(self.source, self.root, "b" * 40, refresh=True)
                        self.assertEqual(result["status"], "blocked")
                        self.assertEqual(len(result["migration_required"]), 2)
                        self.assertEqual(self.snapshot(), before)

    def test_invalid_replacement_paths_never_write(self):
        for relative in (".indexx.json", "logs/install.json", "scripts", "../AGENTS.md", "./AGENTS.md", "/AGENTS.md", "wiki/index.md"):
            with self.subTest(path=relative), self.assertRaisesRegex(ValueError, "exact relative path"):
                self.run_install(replace_support=(relative,))
            self.assertFalse(self.root.exists())

    def test_catalog_cannot_collide_with_library_support_or_data(self):
        self.root.mkdir()
        for relative in ("AGENTS.md", "agents.md", ".indexx.json", ".INDEXX.JSON", "logs/install.json", "scripts", "scripts/catalog.md", "media/saves.md", "wiki/sources/saves.md", "catalog", "markdown", ".git/objects/catalog"):
            for selector in ("legacy", "catalog"):
                with self.subTest(path=relative, selector=selector):
                    config = {"paths": {"use_catalog": selector, "instagram_catalog_legacy" if selector == "legacy" else "instagram_catalog": relative}}
                    (self.root / ".indexx.json").write_text(json.dumps(config))
                    before = self.snapshot()
                    with self.assertRaisesRegex(ValueError, "collides"):
                        self.run_install()
                    self.assertEqual(self.snapshot(), before)

    def test_custom_nested_catalog_is_supported(self):
        self.root.mkdir()
        (self.root / ".indexx.json").write_text(json.dumps({"paths": {"instagram_catalog_legacy": "personal/nested/my-saves.md"}}))
        result = self.run_install()
        self.assertEqual(result["status"], "installed")
        self.assertEqual((self.root / "personal/nested/my-saves.md").read_text(), (self.source / "examples/saves-index.example.md").read_text())

    def test_check_cli_reports_real_compatibility_and_nonzero_on_block(self):
        self.run_install()
        (self.root / "AGENTS.md").write_text("legacy unmanaged support")
        before = self.snapshot()
        with mock.patch.object(installer, "SOURCE", self.source), mock.patch.object(installer, "source_revision", return_value=REVISION), mock.patch.object(installer, "preflight", return_value=[]), mock.patch.object(installer.sys, "argv", ["indexx_install.py", "--root", str(self.root), "--revision", REVISION, "--check", "--refresh-support"]), mock.patch("builtins.print") as output:
            self.assertEqual(installer.main(), 1)
        result = json.loads(output.call_args.args[0])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("AGENTS.md", result["conflicts"])
        self.assertEqual(self.snapshot(), before)

    def test_bad_config_and_directory_collision_stop_before_scaffolding(self):
        self.root.mkdir()
        (self.root / ".indexx.json").write_text("not json")
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse((self.root / "catalog").exists())
        (self.root / ".indexx.json").unlink()
        (self.root / "logs").write_text("unexpected file")
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse((self.root / "catalog").exists())

    def test_symlink_escape_never_writes_outside_library(self):
        self.root.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "scripts").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.run_install()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.root / "catalog").exists())

    def test_source_symlink_cannot_import_unpinned_files(self):
        external = self.base / "external.py"
        external.write_text("unreviewed code")
        script = self.source / "scripts/indexx_progress.py"
        script.unlink()
        script.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "source must not redirect"):
            self.run_install()
        self.assertFalse(self.root.exists())

    def test_install_refuses_source_tree_and_implicit_move(self):
        with self.assertRaises(ValueError):
            installer.install(self.source, self.source, REVISION)
        with self.assertRaises(ValueError):
            installer.install(self.source, self.base, REVISION)
        self.root.mkdir()
        (self.root / ".indexx.json").write_text(json.dumps({"root": str(self.base / "other")}))
        with self.assertRaisesRegex(ValueError, "relocation"):
            self.run_install()

    def test_invalid_existing_root_is_not_preserved_as_success(self):
        self.root.mkdir()
        for invalid in (None, "", 42):
            with self.subTest(root=invalid):
                (self.root / ".indexx.json").write_text(json.dumps({"root": invalid}))
                with self.assertRaisesRegex(ValueError, "nonempty path"):
                    self.run_install()
                self.assertFalse((self.root / "scripts").exists())

    def test_template_parent_collision_is_detected_before_support_changes(self):
        (self.root / "wiki").mkdir(parents=True)
        (self.root / "wiki/taxonomies").write_text("custom file")
        with self.assertRaisesRegex(ValueError, "Expected a directory"):
            self.run_install()
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / "scripts").exists())

    def test_preflight_detects_wrong_computer_and_missing_tools(self):
        with mock.patch.object(installer.sys, "platform", "linux"), mock.patch.object(installer.shutil, "which", return_value=None):
            problems = installer.preflight(self.root)
        self.assertEqual(len(problems), 4)
        self.assertFalse(self.root.exists())

    @unittest.skipUnless(shutil.which("git"), "git required for source provenance test")
    def test_revision_validation_rejects_wrong_or_dirty_checkout(self):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.source), *args], text=True, stderr=subprocess.PIPE).strip()
        git("init", "--quiet")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture")
        actual = git("rev-parse", "HEAD")
        self.assertEqual(installer.source_revision(self.source, actual), actual)
        with self.assertRaises(ValueError):
            installer.source_revision(self.source, REVISION)
        (self.source / "AGENTS.md").write_text("uncommitted instructions")
        with self.assertRaisesRegex(ValueError, "uncommitted"):
            installer.source_revision(self.source, actual)
        (self.source / "AGENTS.md").write_text("support v1\n")
        (self.source / "scripts/indexx_status.py").write_text("# uncommitted parser dependency\n")
        with self.assertRaisesRegex(ValueError, "uncommitted"):
            installer.source_revision(self.source, actual)


if __name__ == "__main__":
    unittest.main()
