"""Conservative format migration with real on-disk fixtures, no external calls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import indexx_migrate as migration
from indexx_status import parse_catalog


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="indexx-migration-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "library"
        self.root.mkdir()
        self.config_path = self.root / ".indexx.json"
        self.catalog = self.root / "markdown/instagram/custom-saves.md"
        self.catalog.parent.mkdir(parents=True)
        self.config = {"root": str(self.root), "paths": {
            "use_catalog": "legacy", "instagram_catalog_legacy": "markdown/instagram/custom-saves.md",
            "instagram_catalog": "catalog/unused.md"}, "stt": {"provider": "elevenlabs"},
            "batch": {"download_n": 7}, "custom_setting": {"untouched": True}}
        self.save_config()
        self.write_catalog([("Pending", "active")])

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config, indent=4) + "\n")

    def write_catalog(self, rows, extra_headers="", extra_values=""):
        text = ('---\nnewest_shortcode: "cursor-unchanged"\ncount: 904\n'
                'watermark_shortcodes: ["first", "second"]\n---\n\n# Saved\n\n'
                '| shortcode | url | type | status | note' + extra_headers + ' |\n'
                '| --- | --- | --- | --- | ---' + (' | ---' * extra_headers.count('|')) + ' |\n')
        for item_id, status in rows:
            text += f'| {item_id} | https://www.instagram.com/reel/{item_id}/ | reel | {status} | keep \\| this{extra_values} |\n'
        text += '\n<!-- crawl cursor stays here -->\nAfter-table text.\n'
        self.catalog.write_text(text)
        return text

    def info(self, item_id="Complete", directory=None, **overrides):
        folder = self.root / (directory or f"media/instagram/creator/2026-09-19_{item_id}")
        folder.mkdir(parents=True, exist_ok=True)
        value = {"platform": "instagram", "id": item_id, "source_url": f"https://www.instagram.com/reel/{item_id}/"}
        value.update(overrides)
        (folder / "info.json").write_text(json.dumps(value))
        return folder

    def rows(self):
        return parse_catalog(self.catalog.read_text())

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_default_plan_is_read_only_and_cli_defaults_to_plan(self):
        before = self.snapshot()
        report = migration.plan_migration(self.root)
        self.assertEqual(report["mode"], "plan")
        self.assertEqual(report["active_statuses_converted"], {"discovered": 1})
        self.assertEqual(report["columns_added"], ["media_path", "legacy_status"])
        result = subprocess.run([sys.executable, str(SCRIPTS / "indexx_migrate.py"), "--root", str(self.root)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["mode"], "plan")
        self.assertEqual(self.snapshot(), before)

    def test_904_rows_preserve_order_extra_columns_cursors_and_complete_claims(self):
        rows = [(f"Done{n}", "wiki_ingested") for n in range(16)] + [(f"Pending{n}", "active") for n in range(888)]
        original = self.write_catalog(rows)
        for n in range(16):
            self.info(f"Done{n}")
        before_config = self.config_path.read_bytes()
        report = migration.apply_migration(self.root)
        current = self.rows()
        self.assertEqual(len(current), 904)
        self.assertEqual([r["shortcode"] for r in current], [r[0] for r in rows])
        self.assertTrue(all(r["note"] == "keep | this" for r in current))
        self.assertTrue(all(r["status"] == "wiki_ingested" for r in current[:16]))
        self.assertTrue(all(r["status"] == "discovered" and r["legacy_status"] == "active" for r in current[16:]))
        self.assertEqual(report["completed_claims_preserved"], 16)
        self.assertEqual(report["artifact_audit"], "not_run")
        self.assertEqual(report["media_paths_added"], 16)
        self.assertEqual(report["active_statuses_converted"], {"discovered": 888})
        after = self.catalog.read_text()
        self.assertEqual(after.split('| shortcode')[0], original.split('| shortcode')[0])
        self.assertEqual(after.split('<!-- crawl cursor')[1], original.split('<!-- crawl cursor')[1])
        self.assertEqual(self.config_path.read_bytes(), before_config)
        self.assertEqual(Path(report["backup_files"][report["catalog"]]).read_text(), original)
        self.assertEqual(Path(report["backup_files"][".indexx.json"]).read_bytes(), before_config)
        self.assertFalse((self.root / "catalog/unused.md").exists())

    def test_only_verified_identity_maps_media_and_active_remains_partial(self):
        self.write_catalog([("Processed", "active"), ("Pending", "active")])
        folder = self.info("Processed", directory="media/instagram/arbitrary/unrelated-name")
        media = folder / "media.mp4"
        media.write_bytes(b"original-media")
        transcript = folder / "transcript.md"
        transcript.write_text("original transcript")
        report = migration.apply_migration(self.root)
        processed, pending = self.rows()
        self.assertEqual(processed["status"], "partial")
        self.assertEqual(processed["legacy_status"], "active")
        self.assertEqual(processed["media_path"], folder.relative_to(self.root).as_posix())
        self.assertEqual(pending["status"], "discovered")
        self.assertEqual(pending["media_path"], "")
        self.assertEqual(media.read_bytes(), b"original-media")
        self.assertEqual(transcript.read_text(), "original transcript")
        self.assertEqual(report["active_statuses_converted"], {"partial": 1, "discovered": 1})

    def test_rerun_is_exact_noop_without_another_backup(self):
        self.info("Pending")
        first = migration.apply_migration(self.root)
        before = self.snapshot()
        second = migration.apply_migration(self.root)
        self.assertEqual(second["mode"], "no_changes")
        self.assertEqual(second["changed_files"], [])
        self.assertIsNone(second["backup"])
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(Path(first["backup"]).is_dir())

    def test_crlf_and_unchanged_cell_formatting_are_preserved(self):
        data = self.catalog.read_bytes().replace(b'\n', b'\r\n').replace(b'| Pending |', b'|   Pending   |')
        self.catalog.write_bytes(data)
        migration.apply_migration(self.root)
        after = self.catalog.read_bytes()
        self.assertEqual(after.count(b'\r\n'), after.count(b'\n'))
        self.assertIn(b'|   Pending   |', after)
        self.assertTrue(after.startswith(data.split(b'| shortcode')[0]))

    def test_header_words_in_extra_data_columns_are_preserved(self):
        self.write_catalog([('Pending', 'active')], ' | field', ' | shortcode')
        migration.apply_migration(self.root)
        self.assertEqual(self.rows()[0]['field'], 'shortcode')
        self.assertEqual(self.rows()[0]['note'], 'keep | this')

    def test_case_aliases_of_reserved_paths_are_rejected_before_reading_catalog(self):
        for relative in ('agents.md', 'README.MD', 'LOGS/catalog.md', '.AGENTS/catalog.md'):
            with self.subTest(path=relative):
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self.catalog.read_bytes())
                self.config['paths']['instagram_catalog_legacy'] = relative
                self.save_config()
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'collides'):
                    migration.apply_migration(self.root)
                self.assertEqual(self.snapshot(), before)

    def test_completed_unmapped_item_blocks_all_writes(self):
        self.write_catalog([("Missing", "wiki_ingested"), ("Pending", "active")])
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Completed claim Missing"):
            migration.apply_migration(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_ambiguous_metadata_or_identity_mismatch_blocks_without_writes(self):
        first = self.info("Pending")
        second = self.info("Pending", directory="media/instagram/other/duplicate")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            migration.apply_migration(self.root)
        self.assertEqual(self.snapshot(), before)
        (second / "info.json").unlink()
        (first / "info.json").write_text(json.dumps({"id": "Pending", "platform": "instagram", "source_url": "https://www.instagram.com/p/Other/"}))
        with self.assertRaisesRegex(ValueError, "Unverified"):
            migration.plan_migration(self.root)

    def test_identity_alias_conflicts_and_wrong_platform_are_rejected(self):
        for overrides in ({"shortcode": "Other"}, {"url": "https://www.instagram.com/p/Other/"}, {"platform": "other"}):
            with self.subTest(overrides=overrides):
                self.info("Pending", **overrides)
                with self.assertRaisesRegex(ValueError, "Unverified"):
                    migration.plan_migration(self.root)

    def test_malformed_duplicate_and_unknown_status_tables_are_rejected(self):
        for rows in ([('Dup', 'active'), ('Dup', 'active')], [('Pending', 'mystery')]):
            self.write_catalog(rows)
            with self.assertRaises(ValueError):
                migration.apply_migration(self.root)
        self.write_catalog([('Pending', 'active')])
        original = self.catalog.read_text()
        for malformed in (original.replace('reel | active', 'reel | extra | active'), original.replace('| --- | --- |', '| --- |', 1), original.replace('Pending/ |', 'Other/ |'), original.replace('keep \\| this |', 'keep this'), original + '| Other | row |\n'):
            self.catalog.write_text(malformed)
            with self.assertRaises(ValueError):
                migration.plan_migration(self.root)
        self.assertFalse((self.root / 'logs').exists())

    def test_escaped_final_pipe_cannot_terminate_a_row_and_never_changes_inputs(self):
        original = self.write_catalog([('Pending', 'active')])
        malformed = original.replace('keep \\| this |', 'ends with escaped ' + r'\|')
        self.assertNotEqual(malformed, original)
        self.catalog.write_text(malformed)
        before = self.snapshot()
        for action in (migration.plan_migration, migration.apply_migration):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(ValueError, 'unescaped pipe'):
                    action(self.root)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.root / 'logs').exists())

    def test_literal_final_pipe_with_a_real_terminator_is_preserved(self):
        original = self.write_catalog([('Pending', 'active')])
        self.catalog.write_text(original.replace('keep \\| this |', 'literal ' + r'\|' + ' |'))
        migration.apply_migration(self.root)
        self.assertEqual(self.rows()[0]['note'], 'literal |')
        self.assertIn('literal ' + r'\|' + ' |', self.catalog.read_text())

    def test_conflicting_legacy_status_is_not_overwritten(self):
        self.write_catalog([('Pending', 'active')], ' | legacy_status', ' | something-else')
        with self.assertRaisesRegex(ValueError, "Conflicting legacy_status"):
            migration.plan_migration(self.root)

    def test_existing_media_reference_requires_matching_identity(self):
        self.write_catalog([('Pending', 'active')], ' | media_path', ' | media/instagram/wrong/folder')
        self.info('Pending')
        with self.assertRaisesRegex(ValueError, "Existing media_path"):
            migration.plan_migration(self.root)

    def test_existing_media_file_reference_is_preserved_and_idempotent(self):
        folder = self.info('Complete')
        media = folder / 'media.mp4'
        media.write_bytes(b'keep this media')
        relative = media.relative_to(self.root).as_posix()
        self.write_catalog([('Complete', 'wiki_ingested')], ' | media_path', ' | ' + relative)
        before = self.snapshot()
        first = migration.apply_migration(self.root)
        second = migration.apply_migration(self.root)
        self.assertEqual(first['mode'], 'no_changes')
        self.assertEqual(second['mode'], 'no_changes')
        self.assertEqual(self.rows()[0]['media_path'], relative)
        self.assertEqual(self.snapshot(), before)

    def test_current_catalog_and_unselected_provider_can_be_noop(self):
        self.config['stt']['provider'] = None
        self.save_config()
        self.write_catalog([('Pending', 'discovered')], ' | media_path', ' | ')
        before = self.snapshot()
        report = migration.apply_migration(self.root)
        self.assertEqual(report['mode'], 'no_changes')
        self.assertEqual(self.snapshot(), before)

    def test_legacy_provider_requires_explicit_selection_and_preserves_other_settings(self):
        self.config['stt'] = {'primary': 'grok-voice-transcribe-2.0', 'fallback': 'elevenlabs_scribe_v2', 'locale': 'en'}
        self.save_config()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'explicit --provider'):
            migration.apply_migration(self.root)
        self.assertEqual(self.snapshot(), before)
        report = migration.apply_migration(self.root, provider='elevenlabs')
        after = json.loads(self.config_path.read_text())
        self.assertEqual(after['stt'], {'provider': 'elevenlabs', 'locale': 'en'})
        self.assertEqual(after['batch'], self.config['batch'])
        self.assertEqual(after['paths'], self.config['paths'])
        self.assertEqual(after['custom_setting'], self.config['custom_setting'])
        self.assertEqual(Path(report['backup_files']['.indexx.json']).read_bytes(), before['.indexx.json'])

    def test_legacy_invalid_or_absent_provider_is_never_inferred(self):
        for stt in ({'provider': 'elevenlabs_scribe_v2'}, {}, {'provider': None, 'primary': 'grok'}, 'legacy'):
            with self.subTest(stt=stt):
                self.config['stt'] = stt
                self.save_config()
                with self.assertRaisesRegex(ValueError, 'explicit --provider'):
                    migration.plan_migration(self.root)
                self.assertEqual(migration.plan_migration(self.root, 'elevenlabs')['provider'], 'elevenlabs')

    def test_valid_provider_automatically_retires_obsolete_defaults_without_switching(self):
        for chosen in ('grok', 'elevenlabs'):
            with self.subTest(chosen=chosen):
                self.config['stt'] = {'provider': chosen, 'primary': 'contradictory-old-default',
                                      'fallback': 'obsolete-fallback', 'locale': 'en'}
                self.save_config()
                original = self.config_path.read_bytes()
                plan = migration.plan_migration(self.root)
                self.assertEqual(plan['provider'], chosen)
                self.assertTrue(plan['provider_config_changed'])
                self.assertEqual(self.config_path.read_bytes(), original)
                different = 'elevenlabs' if chosen == 'grok' else 'grok'
                with self.assertRaisesRegex(ValueError, 'cannot switch'):
                    migration.apply_migration(self.root, different)
                self.assertEqual(self.config_path.read_bytes(), original)
                applied = migration.apply_migration(self.root)
                self.assertEqual(json.loads(self.config_path.read_text())['stt'], {'provider': chosen, 'locale': 'en'})
                self.assertEqual(Path(applied['backup_files']['.indexx.json']).read_bytes(), original)
                self.assertFalse(migration.plan_migration(self.root)['provider_config_changed'])

    def test_valid_provider_cannot_be_switched_by_migration(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'cannot switch'):
            migration.apply_migration(self.root, 'grok')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(migration.plan_migration(self.root, 'elevenlabs')['provider_config_changed'])

    def test_catalog_collisions_and_escaping_paths_are_rejected(self):
        for path in ('README.md', '.indexx.json', 'scripts/indexx_status.py', '.codex/instructions.md', '.agents/settings.md', 'logs/install.json', 'logs/migrations/x.md', 'wiki/index.md', 'catalog', 'markdown', '.', '../outside.md', str(self.root.parent / 'outside.md'), str(self.catalog)):
            with self.subTest(path=path):
                self.config['paths']['instagram_catalog_legacy'] = path
                self.save_config()
                with self.assertRaises(ValueError):
                    migration.plan_migration(self.root)
        self.assertFalse((self.root / 'logs').exists())

    def test_symlink_catalog_config_media_and_backup_paths_are_rejected(self):
        external = self.root.parent / 'external'
        external.mkdir()
        external_file = external / 'catalog.md'
        external_file.write_bytes(self.catalog.read_bytes())
        self.catalog.unlink()
        self.catalog.symlink_to(external_file)
        with self.assertRaisesRegex(ValueError, 'escapes|Symlink'):
            migration.apply_migration(self.root)
        self.catalog.unlink()
        self.write_catalog([('Pending', 'active')])
        for relative in ('media', 'logs'):
            path = self.root / relative
            path.symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'escapes|Symlink'):
                migration.plan_migration(self.root)
            path.unlink()
        config = self.config_path.read_bytes()
        external_config = external / 'config.json'
        external_config.write_bytes(config)
        self.config_path.unlink()
        self.config_path.symlink_to(external_config)
        with self.assertRaisesRegex(ValueError, 'escapes|Symlink'):
            migration.plan_migration(self.root)
        self.assertEqual(external_file.read_bytes(), self.catalog.read_bytes())

    def test_symlink_media_metadata_cannot_supply_identity(self):
        folder = self.info('Pending')
        info = folder / 'info.json'
        outside = self.root.parent / 'external-info.json'
        outside.write_bytes(info.read_bytes())
        info.unlink()
        info.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'escapes|Symlink'):
            migration.plan_migration(self.root)

    def test_logs_file_and_manifest_directory_stop_before_changes(self):
        before = self.catalog.read_bytes()
        logs = self.root / 'logs'
        logs.write_text('a file')
        with self.assertRaisesRegex(ValueError, 'directory'):
            migration.apply_migration(self.root)
        logs.unlink()
        (logs / 'install.json').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'must be a file'):
            migration.apply_migration(self.root)
        self.assertEqual(self.catalog.read_bytes(), before)

    def test_backups_exist_before_first_original_is_written(self):
        original = self.catalog.read_bytes()
        real_write = migration.atomic_write
        def observed_write(path, data):
            backups = list((self.root / 'logs/migrations').glob('*/originals'))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / self.catalog.relative_to(self.root)).read_bytes(), original)
            self.assertEqual((backups[0] / '.indexx.json').read_bytes(), self.config_path.read_bytes())
            real_write(path, data)
        with patch.object(migration, 'atomic_write', side_effect=observed_write):
            migration.apply_migration(self.root)

    def test_catalog_named_report_does_not_collide_with_backup_report(self):
        self.config['paths']['instagram_catalog_legacy'] = 'report.json'
        self.save_config()
        target = self.root / 'report.json'
        original = self.catalog.read_bytes()
        target.write_bytes(original)
        report = migration.apply_migration(self.root)
        self.assertEqual(Path(report['backup_files']['report.json']).read_bytes(), original)
        self.assertEqual(json.loads((Path(report['backup']) / 'report.json').read_text())['mode'], 'applied')

    def test_relative_or_different_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'absolute'):
            migration.plan_migration(Path('relative'))
        self.config['root'] = str(self.root.parent / 'other-library')
        self.save_config()
        with self.assertRaisesRegex(ValueError, 'another root'):
            migration.plan_migration(self.root)


if __name__ == '__main__':
    unittest.main()
