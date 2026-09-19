"""End-to-end local search with exact annotations, cache freshness and safe reads."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import indexx_search as searcher


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="indexx-search-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'library'
        self.root.mkdir()
        self.rows = []
        self.config = {'root': str(self.root), 'paths': {'use_catalog': 'catalog', 'instagram_catalog': 'catalog/saves.md'}}
        self.write('.indexx.json', json.dumps(self.config))
        self.person('alan-watts', 'Alan Watts', ['Watts', 'A. Watts'], ['Speaking', 'Mentioned', 'Featured'])
        self.item('Speaking', handle='archive_uploader', caption='A lecture about attention and awareness.', transcript='Life is a dance, not a destination. Café 東京.', people=[self.annotation('speaker')], reviewed=True)
        self.item('Mentioned', handle='another_uploader', transcript='We mentioned Alan Watts while discussing attention.', people=[self.annotation('mentioned')], reviewed=True)
        self.item('Featured', handle='archive_uploader', people=[self.annotation('featured')], reviewed=True)
        self.item('UploaderOnly', handle='alan_watts', caption='Alan Watts fan account; uploader is not a speaker.')
        self.item('Backlog', handle='pending_uploader', media=False, kind='image')
        self.save_catalog()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def document(self, front, body):
        return '---\n' + '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in front.items()) + '\n---\n' + body

    def person(self, slug, name, aliases, ids):
        return self.write(f'wiki/entities/people/{slug}.md', self.document({'id': slug, 'name': name, 'aliases': aliases}, '# ' + name + '\n\nExplicit citations: ' + ' '.join(f'[[sources/instagram/{item_id}]]' for item_id in ids)))

    def annotation(self, role, slug='alan-watts', name='Alan Watts'):
        return {'id': slug, 'name': name, 'role': role, 'evidence': 'The caption explicitly identifies this person and role.'}

    def item(self, item_id, handle='', caption='', transcript='', people=None, reviewed=None, media=True, kind='reel'):
        relative = f'media/instagram/{handle or "creator"}/2026-09-19_{item_id}' if media else ''
        row = {'shortcode': item_id, 'url': f'https://www.instagram.com/reel/{item_id}/', 'type': kind,
               'status': 'wiki_ingested' if people is not None else 'discovered', 'media_path': relative, 'handle': handle}
        self.rows.append(row)
        if media:
            info = {'id': item_id, 'platform': 'instagram', 'source_url': row['url'], 'handle': handle, 'type': 'video', 'caption': caption}
            self.write(relative + '/info.json', json.dumps(info))
            if transcript:
                self.write(relative + '/transcript.md', self.document({'source': 'grok_stt'}, transcript))
            self.write(relative + '/media.mp4', 'bytes that search must never open')
        if people is not None or reviewed is not None:
            front = {'id': item_id, 'platform': 'instagram', 'handle': handle, 'title': 'Notes for ' + item_id}
            if people is not None:
                front['people'] = people
            if reviewed is not None:
                front['people_reviewed'] = reviewed
            self.write(f'wiki/sources/instagram/{item_id}.md', self.document(front, '# Notes for ' + item_id + '\n\nA supported discussion of awareness.'))
        return row

    def save_catalog(self):
        keys = ['shortcode', 'url', 'type', 'status', 'media_path', 'handle']
        text = '| ' + ' | '.join(keys) + ' |\n| ' + ' | '.join('---' for _ in keys) + ' |\n'
        text += ''.join('| ' + ' | '.join(row[key] for key in keys) + ' |\n' for row in self.rows)
        self.write('catalog/saves.md', text)

    def build(self):
        return searcher.build_index(self.root)

    def ids(self, result):
        return [item['id'] for item in result['results']]

    def test_explicit_people_roles_are_separate_from_uploader_and_text_mentions(self):
        self.build()
        result = searcher.search(self.root, person='Alan Watts')
        self.assertEqual(self.ids(result), ['Featured', 'Mentioned', 'Speaking'])
        self.assertEqual(result['total'], 3)
        self.assertEqual(self.ids(searcher.search(self.root, person='watts', role='speaker')), ['Speaking'])
        self.assertEqual(self.ids(searcher.search(self.root, person='alan-watts', role='featured')), ['Featured'])
        self.assertEqual(self.ids(searcher.search(self.root, role='mentioned')), ['Mentioned'])
        self.assertEqual(self.ids(searcher.search(self.root, uploader='@ALAN_WATTS')), ['UploaderOnly'])
        self.assertEqual(searcher.search(self.root, person='Alan Watts', uploader='alan_watts')['total'], 0)

    def test_catalog_rows_and_coverage_include_backlog_and_unreviewed(self):
        report = self.build()
        result = searcher.search(self.root)
        self.assertEqual(result['total'], 5)
        self.assertEqual(result['coverage'], {'catalog_total': 5, 'wiki_sources': 3, 'people_reviewed': 3, 'unreviewed': 2})
        backlog = next(item for item in result['results'] if item['id'] == 'Backlog')
        self.assertEqual(backlog['people'], [])
        self.assertIsNone(backlog['video_path'])
        self.assertIsNone(backlog['source_path'])
        self.assertEqual(report['coverage'], result['coverage'])
        self.assertEqual(self.ids(searcher.search(self.root, media_type='image')), ['Backlog'])

    def test_caption_transcript_source_and_wiki_pages_are_full_text_searchable(self):
        self.write('wiki/concepts/attention.md', '# Attention\n\nA concept about attention and practice.')
        self.write('wiki/syntheses/awareness.md', '# Awareness\n\nA synthesis of attention practice.')
        self.write('wiki/entities/creators/creator.md', '# Creator\n\nAn uploader interested in attention.')
        self.build()
        result = searcher.search(self.root, 'attention')
        self.assertEqual(set(self.ids(result)), {'Mentioned', 'Speaking'})
        self.assertEqual(result['wiki_total'], 3)
        self.assertEqual(len(result['wiki_results']), 3)
        self.assertEqual(self.ids(searcher.search(self.root, '"Life is a dance"')), ['Speaking'])
        self.assertEqual(self.ids(searcher.search(self.root, 'Café 東京')), ['Speaking'])
        self.assertEqual(searcher.search(self.root, 'awareness')['total'], 3)
        self.assertEqual(searcher.search(self.root, 'attention', person='Alan Watts')['wiki_results'], [])

    def test_punctuation_and_fts_operators_are_literal_and_sql_is_parameterized(self):
        self.build()
        self.assertEqual(self.ids(searcher.search(self.root, '"Life is a dance"!!!')), ['Speaking'])
        for query in ('attention OR nonexistent', '"; DROP TABLE items; --', 'near(attention)'):
            result = searcher.search(self.root, query)
            self.assertEqual(result['total'], 0)
        self.assertEqual(self.ids(searcher.search(self.root, 'attention NOT awareness')), ['Speaking'])
        self.assertEqual(searcher.search(self.root)['total'], 5)
        with self.assertRaisesRegex(ValueError, 'searchable word'):
            searcher.search(self.root, '*** ""')

    def test_exact_name_alias_resolution_and_ambiguity(self):
        self.person('other-person', 'Other Person', ['Watts'], ['Backlog'])
        self.build()
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            searcher.search(self.root, person='Watts')
        self.assertEqual(searcher.search(self.root, person='A. WATTS')['total'], 3)
        self.assertEqual(searcher.search(self.root, person='alan-watts')['total'], 3)
        self.assertEqual(searcher.search(self.root, person='Alan')['total'], 0)
        self.assertEqual(searcher.search(self.root, person="Alan Watts' OR 1=1 --")['total'], 0)

    def test_pagination_counts_every_match_not_only_default_page(self):
        ids = [f'Extra{n:03}' for n in range(75)]
        self.person('alan-watts', 'Alan Watts', ['Watts'], ['Speaking', 'Mentioned', 'Featured'] + ids)
        for item_id in ids:
            self.item(item_id, people=[self.annotation('speaker')], reviewed=True, media=False)
        self.save_catalog()
        self.build()
        result = searcher.search(self.root, person='Alan Watts', role='speaker')
        self.assertEqual(result['total'], 76)
        self.assertEqual(len(result['results']), 20)
        every = searcher.search(self.root, person='Alan Watts', role='speaker', limit=None)
        self.assertEqual(len(every['results']), 76)
        second = searcher.search(self.root, person='Alan Watts', role='speaker', offset=20, limit=20)
        self.assertEqual(second['results'], every['results'][20:40])
        self.assertEqual(searcher.search(self.root, person='Alan Watts', offset=1000)['results'], [])

    def test_reviewed_empty_list_is_counted_and_invalid_annotations_are_not_guessed(self):
        self.item('ReviewedEmpty', people=[], reviewed=True, media=False)
        self.item('InvalidPerson', people=[self.annotation('speaker', slug='missing-person', name='Unknown')], reviewed=True, media=False)
        self.save_catalog()
        result = self.build()
        self.assertEqual(result['coverage']['people_reviewed'], 4)
        self.assertTrue(any('missing-person' in warning for warning in result['warnings']))
        found = searcher.search(self.root)
        invalid = next(item for item in found['results'] if item['id'] == 'InvalidPerson')
        self.assertEqual(invalid['people'], [])
        self.assertEqual(searcher.search(self.root, person='Unknown')['total'], 0)

    def test_invalid_source_identity_cannot_attach_people(self):
        self.write('wiki/sources/instagram/Speaking.md', self.document({'id': 'Wrong', 'platform': 'instagram', 'people': [self.annotation('speaker')], 'people_reviewed': True}, 'Wrong identity'))
        report = self.build()
        self.assertEqual(searcher.search(self.root, person='Alan Watts', role='speaker')['total'], 0)
        self.assertEqual(report['coverage']['wiki_sources'], 2)
        self.assertTrue(any('identity does not match' in warning for warning in report['warnings']))

    def test_invalid_metadata_warns_and_does_not_attach_other_item_text(self):
        folder = self.root / self.rows[0]['media_path']
        (folder / 'info.json').write_text(json.dumps({'id': 'Wrong', 'platform': 'instagram', 'source_url': 'https://www.instagram.com/p/Wrong/', 'caption': 'secret wrong content'}))
        self.build()
        self.assertEqual(searcher.search(self.root, 'secret')['total'], 0)
        result = searcher.search(self.root, person='Alan Watts', role='speaker')['results'][0]
        self.assertIsNone(result['video_path'])
        self.assertTrue(searcher.search(self.root)['warnings'])

    def test_changes_to_each_input_make_queries_stale_and_rebuild_restores(self):
        paths = ['.indexx.json', 'catalog/saves.md', self.rows[0]['media_path'] + '/info.json', self.rows[0]['media_path'] + '/transcript.md', 'wiki/sources/instagram/Speaking.md', 'wiki/entities/people/alan-watts.md']
        for relative in paths:
            with self.subTest(relative=relative):
                self.build()
                path = self.root / relative
                before = path.read_bytes()
                path.write_bytes(before + b'\n')
                with self.assertRaisesRegex(ValueError, 'stale.*build'):
                    searcher.search(self.root)
                self.build()
                self.assertTrue(searcher.index_status(self.root)['fresh'])

    def test_new_and_removed_wiki_documents_stale_but_generated_views_do_not(self):
        self.build()
        page = self.write('wiki/concepts/new.md', '# Newly added\n\nA fresh concept.')
        with self.assertRaisesRegex(ValueError, 'stale'):
            searcher.search(self.root)
        self.build()
        page.unlink()
        with self.assertRaisesRegex(ValueError, 'stale'):
            searcher.search(self.root)
        self.build()
        self.write('wiki/views/watchlist.md', '# Generated\n\nThis is a local generated view.')
        self.assertTrue(searcher.index_status(self.root)['fresh'])
        self.assertEqual(searcher.search(self.root, 'Generated')['wiki_total'], 0)
        self.build()
        self.write('wiki/views/watchlist.md', 'Changed generated view.')
        self.assertTrue(searcher.index_status(self.root)['fresh'])

    def test_media_availability_changes_invalidate_without_reading_media(self):
        self.build()
        video = self.root / self.rows[0]['media_path'] / 'media.mp4'
        video.unlink()
        with self.assertRaisesRegex(ValueError, 'stale'):
            searcher.search(self.root)
        self.build()
        result = searcher.search(self.root, person='Alan Watts', role='speaker')['results'][0]
        self.assertIsNone(result['video_path'])

    def test_query_freshness_does_not_reread_transcript_or_wiki_bytes(self):
        self.build()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('query should stat, not read content')):
            result = searcher.search(self.root, 'attention')
            self.assertEqual(result['total'], 2)
            self.assertTrue(searcher.index_status(self.root)['fresh'])

    def test_build_never_reads_media_bytes_and_keeps_sources_unchanged(self):
        original_reader = Path.read_bytes
        before = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        def guarded(path):
            if path.suffix in ('.mp4', '.mp3', '.jpg'):
                raise AssertionError('media bytes must not be opened')
            return original_reader(path)
        with patch.object(Path, 'read_bytes', guarded):
            self.build()
        for path, data in before.items():
            self.assertEqual(Path(path).read_bytes(), data)

    def test_symlink_metadata_wiki_and_media_paths_are_skipped_without_external_reads(self):
        external = Path(self.temp.name) / 'external'
        external.mkdir()
        secret = external / 'secret.md'
        secret.write_text('UNSAFE_EXTERNAL_TEXT')
        source = self.root / 'wiki/sources/instagram/Speaking.md'
        source.unlink()
        source.symlink_to(secret)
        info = self.root / self.rows[0]['media_path'] / 'info.json'
        info.unlink()
        info.symlink_to(secret)
        (self.root / 'wiki/entities/external').symlink_to(external, target_is_directory=True)
        original_reader = Path.read_bytes
        def guarded(path):
            self.assertNotIn(external, path.resolve().parents)
            return original_reader(path)
        with patch.object(Path, 'read_bytes', guarded):
            report = self.build()
        self.assertTrue(report['warnings'])
        self.assertEqual(searcher.search(self.root, 'UNSAFE_EXTERNAL_TEXT')['total'], 0)
        self.assertEqual(searcher.search(self.root, person='Alan Watts', role='speaker')['total'], 0)

    def test_symlink_output_and_cache_directory_collision_are_rejected(self):
        external = Path(self.temp.name) / 'external-cache'
        external.mkdir()
        (self.root / 'db').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'escapes|Symlink'):
            self.build()
        self.assertEqual(list(external.iterdir()), [])
        (self.root / 'db').unlink()
        (self.root / 'db/search.sqlite3').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'collides'):
            self.build()

    def test_catalog_cannot_be_replaced_by_cache_and_existing_unowned_file_is_preserved(self):
        catalog = (self.root / 'catalog/saves.md').read_bytes()
        self.write('db/search.sqlite3', catalog.decode())
        self.config['paths']['instagram_catalog'] = 'db/search.sqlite3'
        self.write('.indexx.json', json.dumps(self.config))
        with self.assertRaises((ValueError, sqlite3.Error)):
            self.build()
        self.assertEqual((self.root / 'db/search.sqlite3').read_bytes(), catalog)

    def test_video_type_normalizes_reels_and_metadata_resolves_posts(self):
        self.rows[0]['type'] = 'post'
        self.save_catalog()
        self.build()
        self.assertEqual(searcher.search(self.root, media_type='video')['total'], 4)
        result = searcher.search(self.root, person='Alan Watts', role='speaker', media_type='video')
        self.assertEqual(result['results'][0]['catalog_type'], 'post')
        self.assertEqual(result['results'][0]['type'], 'video')
        self.item('UnprocessedReel', media=False)
        self.save_catalog()
        self.build()
        self.assertIn('UnprocessedReel', self.ids(searcher.search(self.root, media_type='video')))

    def test_canonical_id_beats_an_alias_collision(self):
        self.person('other-person', 'Other Person', ['alan-watts'], ['Backlog'])
        self.build()
        self.assertEqual(searcher.search(self.root, person='alan-watts')['total'], 3)

    def test_validated_tags_facets_names_and_aliases_are_searchable(self):
        source = self.root / 'wiki/sources/instagram/Speaking.md'
        text = source.read_text()
        text = text.replace('---\n# Notes', 'tags: ["meditation", "focus", "practice", "quiet", "learning"]\nfacets: {"form":"lecture","topic":["mindfulness"],"intent":"learn"}\n---\n# Notes')
        source.write_text(text)
        self.build()
        self.assertEqual(self.ids(searcher.search(self.root, 'mindfulness meditation')), ['Speaking'])
        self.assertEqual(searcher.search(self.root, '"A. Watts"')['total'], 3)
        self.assertEqual(searcher.search(self.root, '"Alan Watts"', role='speaker')['total'], 1)

    def test_valid_classification_remains_searchable_when_person_annotation_fails(self):
        for people in ([self.annotation('speaker', slug='missing-person', name='Missing Person')], 'malformed'):
            with self.subTest(people=people):
                front = {'id': 'Speaking', 'platform': 'instagram', 'handle': 'archive_uploader',
                         'tags': ['unique-search-tag', 'focus', 'practice', 'quiet', 'learning'],
                         'facets': {'form': 'lecture', 'topic': ['mindfulness'], 'intent': 'learn'},
                         'people': people, 'people_reviewed': True}
                self.write('wiki/sources/instagram/Speaking.md', self.document(front, '# Supported narrative\n\nThe independent classification remains useful.'))
                report = self.build()
                result = searcher.search(self.root, 'unique-search-tag mindfulness')
                self.assertEqual(self.ids(result), ['Speaking'])
                self.assertEqual(result['results'][0]['people'], [])
                self.assertEqual(searcher.search(self.root, person='Alan Watts', role='speaker')['total'], 0)
                self.assertEqual(report['coverage']['people_reviewed'], 2)
                self.assertTrue(any('Speaking.md' in warning for warning in report['warnings']))

    def test_generated_views_case_variants_are_excluded_and_markdown_suffix_is_casefolded(self):
        generated = self.write('wiki/Views/watch.MD', '# GeneratedOnlyTerm\n\nInitial generated watchlist.')
        self.write('wiki/concepts/upper.MD', '# UpperSuffixTerm\n\nSearchable source prose.')
        self.build()
        self.assertEqual(searcher.search(self.root, 'UpperSuffixTerm')['wiki_total'], 1)
        self.assertEqual(searcher.search(self.root, 'GeneratedOnlyTerm')['wiki_total'], 0)
        generated.write_text('Updated generated view with a different length.')
        self.write('wiki/Views/another.md', '# Another generated view')
        self.assertTrue(searcher.index_status(self.root)['fresh'])
        self.assertEqual(searcher.search(self.root, 'generated')['wiki_total'], 0)

    def test_excerpts_show_narrative_without_search_only_aliases_or_raw_markup(self):
        source = self.root / 'wiki/sources/instagram/Speaking.md'
        text = source.read_text().replace('A supported discussion of awareness.', 'He says "stay curious" about [[concepts/attention|attention]] and [practice](../../concepts/practice.md).')
        text = text.replace('---\n# Notes', 'tags: ["unique-search-tag", "focus", "practice", "quiet", "learning"]\nfacets: {"form":"lecture","topic":["mindfulness"],"intent":"learn"}\n---\n# Notes')
        source.write_text(text)
        self.build()
        for query in ('unique-search-tag', '"A. Watts"'):
            result = searcher.search(self.root, query, role='speaker')['results'][0]
            excerpt = result['excerpt']
            self.assertIn('He says "stay curious" about attention and practice.', excerpt)
            for hidden in ('alan-watts', 'A. Watts', 'unique-search-tag', 'archive_uploader', '[[', '](', '# Notes', '"facets"'):
                self.assertNotIn(hidden, excerpt)
            self.assertNotIn('search_text', result)
            self.assertEqual(result['source_path'], 'wiki/sources/instagram/Speaking.md')

    def test_source_uploader_mismatch_cannot_attach_people(self):
        source = self.root / 'wiki/sources/instagram/Speaking.md'
        source.write_text(source.read_text().replace('archive_uploader', 'different_uploader'))
        report = self.build()
        self.assertEqual(searcher.search(self.root, person='Alan Watts', role='speaker')['total'], 0)
        self.assertTrue(any('uploader does not match' in warning for warning in report['warnings']))

    def test_full_text_results_rank_relevant_documents_before_id_order(self):
        self.item('AAAWeak', caption='rareterm ' + 'filler ' * 100, media=True)
        self.item('ZZZStrong', caption='rareterm rareterm rareterm', media=True)
        self.save_catalog()
        self.build()
        self.assertEqual(self.ids(searcher.search(self.root, 'rareterm')), ['ZZZStrong', 'AAAWeak'])

    def test_missing_cache_and_bad_query_options_are_actionable(self):
        with self.assertRaisesRegex(ValueError, 'missing.*build'):
            searcher.search(self.root)
        self.build()
        for kwargs in ({'limit': 0}, {'offset': -1}, {'role': 'uploader'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                searcher.search(self.root, **kwargs)

    def test_cli_build_query_all_and_status(self):
        def call(*arguments):
            output = subprocess.run([sys.executable, str(SCRIPTS / 'indexx_search.py'), *arguments, '--root', str(self.root)], check=True, capture_output=True, text=True)
            return json.loads(output.stdout)
        self.assertEqual(call('build')['coverage']['catalog_total'], 5)
        self.assertEqual(call('query', '--person', 'Alan Watts', '--role', 'speaker', '--all')['total'], 1)
        self.assertTrue(call('status')['fresh'])


if __name__ == '__main__':
    unittest.main()
