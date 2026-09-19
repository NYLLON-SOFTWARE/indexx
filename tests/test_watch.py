import copy
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("indexx_watch", REPO / "scripts/indexx_watch.py")
watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watch)


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="indexx-watch-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "library"
        self.video = self.root / "media/instagram/example/2026-09-19_Clip1/media.mp4"
        self.video.parent.mkdir(parents=True)
        self.video.write_bytes(b"existing local video fixture")
        self.source = self.root / "wiki/sources/instagram/Clip1.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("# Existing wiki source\n")
        self.report = {
            "results": [
                {"id": "Clip1", "platform": "instagram", "title": "A useful clip", "url": "https://www.instagram.com/reel/Clip1/?utm_source=tracking",
                 "handle": "example", "type": "reel", "status": "wiki_ingested", "media_path": str(self.video.parent.relative_to(self.root)),
                 "video_path": str(self.video.relative_to(self.root)), "source_path": str(self.source.relative_to(self.root)),
                 "people": [{"id": "jane-doe", "name": "Jane Doe", "role": "speaker", "evidence": "caption"}], "excerpt": "A source-grounded excerpt."},
                {"id": "Clip2", "platform": "instagram", "title": "A catalog-only match", "url": "https://instagram.com/p/Clip2/",
                 "handle": "another", "type": "video", "status": "discovered", "media_path": "", "video_path": None,
                 "source_path": None, "people": [], "excerpt": ""},
            ],
            "total": 2,
            "coverage": {"catalog_total": 904, "wiki_sources": 16, "people_reviewed": 5, "unreviewed": 899},
            "indexed_at": "2026-09-19T00:00:00Z", "wiki_results": [], "warnings": [],
        }

    def render(self, **kwargs):
        return watch.render_watchlist(self.root, self.report, **kwargs)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_renders_every_match_as_local_html_and_obsidian(self):
        before_video, before_source = self.video.read_bytes(), self.source.read_bytes()
        result = self.render(name="people-clips", title="People clips")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["playable"], 1)
        self.assertEqual(Path(result["html_path"]), self.root / "wiki/views/people-clips.html")
        document = Path(result["html_path"]).read_text()
        markdown = Path(result["markdown_path"]).read_text()
        elements = Elements(document).elements
        videos = [attrs for tag, attrs in elements if tag == "video"]
        self.assertEqual(len(videos), 1)
        self.assertIn("controls", videos[0])
        self.assertNotIn("autoplay", videos[0])
        self.assertEqual(videos[0]["preload"], "metadata")
        self.assertEqual(videos[0]["src"], "../../media/instagram/example/2026-09-19_Clip1/media.mp4")
        self.assertEqual(sum(tag == "article" for tag, _ in elements), 2)
        self.assertIn("![[media/instagram/example/2026-09-19_Clip1/media.mp4]]", markdown)
        self.assertIn("Local video unavailable.", document)
        self.assertIn("Jane Doe (speaker)", document)
        self.assertIn("Uploader: @example", document)
        self.assertIn("5 of 904 catalog clips", document)
        self.assertIn("899 clips are unreviewed", document)
        self.assertIn("Index snapshot: 2026-09-19T00:00:00Z", document)
        self.assertIn("regenerate this watchlist after library changes", document)
        self.assertIn("This is a saved view", markdown)
        self.assertIn("../sources/instagram/Clip1.md", document)
        self.assertIn("https://www.instagram.com/reel/Clip1/", document)
        self.assertNotIn("utm_source", document)
        self.assertNotIn(str(self.root), document)
        self.assertEqual(self.video.read_bytes(), before_video)
        self.assertEqual(self.source.read_bytes(), before_source)

    def test_generated_outputs_can_be_regenerated_without_touching_sources(self):
        first = self.render()
        self.report["results"][0]["title"] = "Updated title"
        second = self.render()
        self.assertEqual(first["html_path"], second["html_path"])
        self.assertIn("Updated title", Path(second["html_path"]).read_text())
        self.assertTrue(Path(second["markdown_path"]).read_text().startswith(watch.MARKER + "\n"))
        self.assertEqual(self.source.read_text(), "# Existing wiki source\n")

    def test_second_staging_write_failure_preserves_published_pair(self):
        result = self.render(title="Previous snapshot")
        before = self.snapshot()
        original_stage = watch.stage_file
        def fail_markdown_write(path, data):
            if path == Path(result["markdown_path"]):
                raise OSError("Injected Markdown staging failure")
            return original_stage(path, data)
        with mock.patch.object(watch, "stage_file", side_effect=fail_markdown_write):
            with self.assertRaisesRegex(OSError, "Markdown staging failure"):
                self.render(title="New snapshot")
        self.assertEqual(self.snapshot(), before)

    def test_second_replacement_failure_restores_previous_pair_or_absence(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    self.render(title="Previous snapshot")
                before = self.snapshot()
                original_replace = watch.os.replace
                def fail_markdown_replace(source, target):
                    if Path(target).name == "watchlist.md":
                        raise OSError("Injected Markdown replacement failure")
                    return original_replace(source, target)
                with mock.patch.object(watch.os, "replace", side_effect=fail_markdown_replace):
                    with self.assertRaisesRegex(OSError, "Markdown replacement failure"):
                        self.render(title="New snapshot")
                self.assertEqual(self.snapshot(), before)

    def test_edit_during_staging_is_preserved_and_stops_both_publications(self):
        result = self.render(title="Previous snapshot")
        html_path, md_path = Path(result["html_path"]), Path(result["markdown_path"])
        previous_html = html_path.read_bytes()
        original_stage = watch.stage_file
        def edit_markdown_after_staging(path, data):
            temporary = original_stage(path, data)
            if path == md_path:
                md_path.write_text("# My curated edit during generation\n")
            return temporary
        with mock.patch.object(watch, "stage_file", side_effect=edit_markdown_after_staging):
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite|destination changed"):
                self.render(title="New snapshot")
        self.assertEqual(html_path.read_bytes(), previous_html)
        self.assertEqual(md_path.read_text(), "# My curated edit during generation\n")
        self.assertEqual({path.name for path in html_path.parent.iterdir()}, {"watchlist.html", "watchlist.md"})

    def test_recovery_failure_retains_original_copy_and_reports_its_location(self):
        result = self.render(title="Previous snapshot")
        html_path = Path(result["html_path"])
        previous_html = html_path.read_bytes()
        original_replace = watch.os.replace
        def fail_markdown_and_rollback(source, target):
            if Path(target).name == "watchlist.md" or ".rollback." in Path(source).name:
                raise OSError("Injected replacement failure")
            return original_replace(source, target)
        with mock.patch.object(watch.os, "replace", side_effect=fail_markdown_and_rollback):
            with self.assertRaisesRegex(OSError, "Original copies retained at") as error:
                self.render(title="New snapshot")
        originals = list(html_path.parent.glob(".watchlist.html.rollback.*"))
        self.assertEqual(len(originals), 1)
        self.assertEqual(originals[0].read_bytes(), previous_html)
        self.assertIn(str(originals[0]), str(error.exception))

    def test_curated_destination_blocks_both_outputs(self):
        result = self.render()
        Path(result["markdown_path"]).write_text("# A curated note\n")
        before = self.snapshot()
        self.report["results"][0]["title"] = "Should not replace HTML either"
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            self.render()
        self.assertEqual(self.snapshot(), before)

    def test_curated_html_is_never_overwritten(self):
        path = self.root / "wiki/views/watchlist.html"
        path.parent.mkdir()
        path.write_text("<h1>Curated gallery</h1>")
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            self.render()
        self.assertEqual(path.read_text(), "<h1>Curated gallery</h1>")
        self.assertFalse(path.with_suffix(".md").exists())

    def test_invalid_names_are_rejected_without_outputs(self):
        for name in ("../other", "a/b", "../index", "Watchlist", "has spaces", "", ".hidden", "a.md"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "slug"):
                self.render(name=name)
        self.assertFalse((self.root / "wiki/views").exists())

    def test_output_symlinks_are_rejected_inside_and_outside_library(self):
        views = self.root / "wiki/views"
        outside = self.base / "outside"
        outside.mkdir()
        views.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.render()
        self.assertEqual(list(outside.iterdir()), [])
        views.unlink()
        views.mkdir()
        (views / "watchlist.md").symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.render()
        self.assertFalse((views / "watchlist.html").exists())
        self.assertEqual(self.source.read_text(), "# Existing wiki source\n")

    def test_all_backend_paths_are_revalidated_before_writes(self):
        for field in ("media_path", "video_path", "source_path"):
            original = self.report["results"][0][field]
            for value in (str(self.base / "outside.mp4"), "../outside.mp4"):
                self.report["results"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "escapes|traversal"):
                    self.render()
                self.assertFalse((self.root / "wiki/views").exists())
            self.report["results"][0][field] = original

    def test_media_symlink_escape_cannot_be_embedded(self):
        target = self.base / "outside.mp4"
        target.write_bytes(b"private external media")
        self.video.unlink()
        self.video.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.render()
        self.assertFalse((self.root / "wiki/views").exists())

    def test_optional_poster_uses_local_file_and_rejects_symlink_escape(self):
        poster = self.video.with_name("poster.jpg")
        poster.write_bytes(b"local poster fixture")
        result = self.render()
        videos = [attrs for tag, attrs in Elements(Path(result["html_path"]).read_text()).elements if tag == "video"]
        self.assertEqual(videos[0]["poster"], "../../media/instagram/example/2026-09-19_Clip1/poster.jpg")
        outside = self.base / "outside.jpg"
        outside.write_bytes(b"private image")
        poster.unlink()
        poster.symlink_to(outside)
        previous_html = Path(result["html_path"]).read_bytes()
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.render()
        self.assertEqual(Path(result["html_path"]).read_bytes(), previous_html)

    def test_titles_people_captions_and_warnings_cannot_inject_markup(self):
        payload = '<img src=x onerror="alert(1)"> [x](javascript:alert(1)) ![[private]]\n# Heading'
        self.report["results"][0].update(title=payload, handle=payload, excerpt=payload)
        self.report["results"][0]["people"] = [{"id": "person", "name": payload, "role": payload}]
        self.report["warnings"] = [payload]
        result = self.render(title=payload)
        document = Path(result["html_path"]).read_text()
        markdown = Path(result["markdown_path"]).read_text()
        self.assertFalse(any(tag in ("img", "script") for tag, _ in Elements(document).elements))
        self.assertNotIn("<img", markdown)
        self.assertNotIn("![[private]]", markdown)
        self.assertNotIn("[x](javascript:", markdown)
        self.assertNotIn("\n# Heading", markdown)
        self.assertIn("&lt;img", document)

    def test_external_links_require_https_instagram_and_matching_clip(self):
        for url in ("javascript:alert(1)", "http://instagram.com/p/Clip1/", "https://evil.example/p/Clip1/", "https://instagram.com.evil.example/p/Clip1/", "https://user@instagram.com/p/Clip1/", "https://instagram.com/p/Other/"):
            self.report["results"][0]["url"] = url
            result = self.render()
            links = [attrs.get("href") for tag, attrs in Elements(Path(result["html_path"]).read_text()).elements if tag == "a"]
            self.assertNotIn(url, links)
            self.assertEqual(sum(link.startswith("https:") for link in links), 1)

    def test_unavailable_or_unsupported_files_do_not_get_fake_players(self):
        for video_path in ("media/missing.mp4", "wiki/sources/instagram/Clip1.md"):
            self.report["results"][0]["video_path"] = video_path
            result = self.render()
            self.assertEqual(result["playable"], 0)
            self.assertNotIn("<video", Path(result["html_path"]).read_text())
        self.video.write_bytes(b"")
        self.report["results"][0]["video_path"] = str(self.video)
        self.assertEqual(self.render()["playable"], 0)

    def test_unsafe_obsidian_embed_filename_uses_encoded_local_link(self):
        unusual = self.video.with_name("a video [draft] #1.mp4")
        self.video.rename(unusual)
        self.report["results"][0]["video_path"] = str(unusual)
        result = self.render()
        document = Path(result["html_path"]).read_text()
        markdown = Path(result["markdown_path"]).read_text()
        encoded = "a%20video%20%5Bdraft%5D%20%231.mp4"
        self.assertIn(encoded, document)
        self.assertIn("[Open local video](<../../media/", markdown)
        self.assertIn(encoded, markdown)
        self.assertNotIn("![[", markdown)

    def test_missing_coverage_is_unknown_and_zero_is_known(self):
        self.report["coverage"] = {}
        result = self.render()
        self.assertIn("coverage is unknown", Path(result["html_path"]).read_text())
        self.report["coverage"] = {"people_reviewed": 0, "catalog_total": 904}
        result = self.render()
        self.assertIn("0 of 904 catalog clips", Path(result["html_path"]).read_text())
        self.assertNotIn("coverage is unknown", Path(result["html_path"]).read_text())

    def test_empty_results_are_valid_but_truncated_results_are_rejected(self):
        self.report["total"] = 3
        with self.assertRaisesRegex(ValueError, "all search results"):
            self.render()
        self.assertFalse((self.root / "wiki/views").exists())
        self.report.update(results=[], total=0)
        result = self.render()
        self.assertEqual(result["count"], 0)
        self.assertIn("No matching clips.", Path(result["html_path"]).read_text())

    def test_cli_passes_all_filters_and_requests_unpaginated_results(self):
        fake_search = mock.Mock(return_value=copy.deepcopy(self.report))
        module = types.ModuleType("indexx_search")
        module.search = fake_search
        arguments = ["indexx_watch.py", "--root", str(self.root), "--person", "jane-doe", "--role", "speaker", "--uploader", "example", "--text", "useful", "--type", "video", "--name", "jane-clips"]
        with mock.patch.dict(sys.modules, {"indexx_search": module}), mock.patch.object(sys, "argv", arguments), mock.patch("builtins.print") as output:
            self.assertEqual(watch.main(), 0)
        fake_search.assert_called_once_with(self.root, query="useful", person="jane-doe", role="speaker", uploader="example", media_type="video", limit=None)
        self.assertEqual(json.loads(output.call_args.args[0])["count"], 2)
        self.assertTrue((self.root / "wiki/views/jane-clips.html").is_file())
        document = (self.root / "wiki/views/jane-clips.html").read_text()
        self.assertIn("jane-doe · speaker · Uploader: @example · video", document)
        self.assertIn("Search: &quot;useful&quot;", document)

    def test_cli_reports_corrupt_search_database_without_traceback(self):
        cache = self.root / "db/search.sqlite3"
        cache.parent.mkdir()
        original = b"not a SQLite database"
        cache.write_bytes(original)
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/indexx_watch.py"), "--root", str(self.root)],
            cwd=self.base, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("Watchlist stopped:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(cache.read_bytes(), original)
        self.assertFalse((self.root / "wiki/views").exists())

    def test_real_search_index_renders_person_filter_and_survives_generated_views(self):
        with mock.patch.object(sys, "path", [str(REPO / "scripts"), *sys.path]):
            from indexx_search import build_index, search
        (self.root / ".indexx.json").write_text(json.dumps({"paths": {"use_catalog": "catalog", "instagram_catalog": "catalog/saves.md"}}))
        catalog = self.root / "catalog/saves.md"
        catalog.parent.mkdir()
        catalog.write_text(
            "| shortcode | url | type | status | media_path |\n| --- | --- | --- | --- | --- |\n"
            "| Clip1 | https://instagram.com/reel/Clip1/ | reel | metadata | media/instagram/example/2026-09-19_Clip1 |\n"
            "| Clip2 | https://instagram.com/p/Clip2/ | video | discovered | |\n"
        )
        self.video.with_name("info.json").write_text(json.dumps({"id": "Clip1", "platform": "instagram", "source_url": "https://instagram.com/reel/Clip1/", "handle": "example"}))
        self.source.write_text(
            '---\nid: "Clip1"\nplatform: instagram\nhandle: example\npeople_reviewed: true\n'
            'people: [{"id":"jane-doe","name":"Jane Doe","role":"speaker","evidence":"Source caption identifies the speaker"}]\n'
            '---\n# A useful clip\nA source-grounded excerpt.\n'
        )
        person = self.root / "wiki/entities/people/jane-doe.md"
        person.parent.mkdir(parents=True)
        person.write_text('---\nid: jane-doe\nname: Jane Doe\naliases: ["Jane"]\n---\n# Jane Doe\nSpeaker cited in [[sources/instagram/Clip1]].\n')
        build_index(self.root)
        report = search(self.root, person="Jane", role="speaker", limit=None)
        result = watch.render_watchlist(self.root, report, title="Jane · speaker")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["playable"], 1)
        self.assertIn("1 of 2 catalog clips", Path(result["html_path"]).read_text())
        self.assertIn("Jane Doe (speaker)", Path(result["html_path"]).read_text())
        self.assertEqual(search(self.root, person="Jane", role="speaker", limit=None)["total"], 1)


if __name__ == "__main__":
    unittest.main()
