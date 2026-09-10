import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_ids.py"
SPEC = importlib.util.spec_from_file_location("export_ids", SCRIPT)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def batch(links, account="example"):
    return {
        "source_url": f"https://www.instagram.com/{account}/saved/all-posts/",
        "captured_at": "2026-09-09T12:00:00Z",
        "links": links,
    }


class ExportTests(unittest.TestCase):
    def test_aliases_merge_while_preserving_case_and_observations(self):
        data = batch([
            {"url": "/p/Example_Ab1/"},
            {"url": "/reel/Example_Ab1/", "badges": ["Clip"]},
            {"url": "/reels/Example_Ab1/"},
            {"url": "/p/example_Ab1/"},
        ])
        result = exporter.normalize([data], "partial", "Synthetic")
        self.assertEqual(result["unique_count"], 2)
        item = result["items"][0]
        self.assertEqual(item["type"], "reel")
        self.assertEqual(len(item["observed_urls"]), 3)
        self.assertEqual(item["badges"], ["Clip"])

    def test_unbadged_and_carousel_tiles_are_retained(self):
        data = batch([{"url": "/p/Plain/"}, {"url": "/p/Slides/", "badges": ["Carousel"]}])
        result = exporter.normalize([data], "partial", "Synthetic")
        self.assertEqual([x["type"] for x in result["items"]], ["post_or_reel", "carousel"])

    def test_numeric_story_ids_stay_strings_and_do_not_collide(self):
        result = exporter.normalize([batch([
            {"url": "/stories/example/12345678901234567890/"},
            {"url": "/p/12345678901234567890/"},
        ])], "partial", "Synthetic")
        self.assertEqual(result["unique_count"], 2)
        self.assertEqual(result["items"][0]["id"], "12345678901234567890")
        self.assertEqual(result["items"][0]["id_kind"], "story_id")
        self.assertIsNone(result["items"][0]["media_id"])

    def test_unresolved_and_offsite_links_remain_visible(self):
        links = [{"url": value} for value in [
            "https://example.com/p/Abc/", "https://www.instagram.com.evil.example/p/Abc/",
            "/stories/highlights/123/", "/example/saved/audio/", "/unknown/Abc/",
        ]]
        result = exporter.normalize([batch(links)], "partial", "Unresolved links")
        self.assertEqual(result["unique_count"], 0)
        self.assertEqual(len(result["unresolved_links"]), len(links))

    def test_mixed_accounts_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Mixed-account"):
            exporter.normalize([batch([], "one"), batch([], "two")], "partial", "Synthetic")

    def test_empty_cannot_hide_items_or_unresolved_links(self):
        for url in ["/p/Example/", "/unknown/Example/"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                exporter.normalize([batch([{"url": url}])], "empty", "Synthetic")

    def test_coverage_is_never_inferred_or_server_verified(self):
        for status in ["partial", "end-observed", "empty"]:
            result = exporter.normalize([batch([])], status, "Caller-supplied evidence")
            self.assertEqual(result["coverage"], {
                "status": status, "reason": "Caller-supplied evidence", "server_total_verified": False,
            })

    def test_cli_emits_three_consistent_files_and_defaults_to_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            run = subprocess.run([
                sys.executable, str(SCRIPT), str(ROOT / "examples/checkpoints.jsonl"),
                "--out-dir", temp, "--reason", "Synthetic example",
            ], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(run.stdout), {"unique_count": 3, "unresolved_count": 0, "status": "partial"})
            output = Path(temp)
            data = json.loads((output / "saved-items.json").read_text())
            with (output / "saved-items.csv").open(newline="") as source:
                rows = list(csv.DictReader(source))
            ids = (output / "saved-ids.txt").read_text().splitlines()
            self.assertEqual(ids, [item["id"] for item in data["items"]])
            self.assertEqual(ids, [row["id"] for row in rows])
            self.assertEqual(data["coverage"]["status"], "partial")

    def test_invalid_source_exits_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "bad.jsonl", Path(temp) / "output"
            data = batch([])
            data["source_url"] = "https://www.instagram.com/example/"
            source.write_text(json.dumps(data) + "\n")
            run = subprocess.run([
                sys.executable, str(SCRIPT), str(source), "--out-dir", str(output), "--reason", "Synthetic",
            ], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
