"""An installed library can find people across uploaders and render every match."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import indexx_install


class WikiFlowTests(unittest.TestCase):
    def test_installed_search_and_watchlist_preserve_sources_and_refresh_membership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "library with spaces"
            indexx_install.install(REPO, root, "a" * 40)
            def put(relative, text):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                return path

            def doc(front, body):
                return "---\n" + "\n".join(f"{k}: {json.dumps(v)}" for k, v in front.items()) + "\n---\n" + body

            put("wiki/entities/people/demo-speaker.md", doc(
                {"id": "demo-speaker", "name": "Demo Speaker", "aliases": ["D. Speaker"]},
                "A synthetic fixture. [[sources/instagram/ClipA]] [[sources/instagram/ClipB]] [[sources/instagram/ClipC]]"))
            rows = []
            fronts = {}
            for item_id, uploader, role in (("ClipA", "uploader_one", "speaker"),
                                             ("ClipB", "uploader_two", "speaker"),
                                             ("ClipC", "uploader_three", "mentioned")):
                folder = f"media/instagram/{uploader}/2026-09-19_{item_id}"
                url = f"https://www.instagram.com/reel/{item_id}/"
                put(folder + "/info.json", json.dumps({"id": item_id, "platform": "instagram", "handle": uploader,
                                                      "source_url": url, "type": "video", "caption": "Demo Speaker"}))
                put(folder + "/transcript.md", "Synthetic text about attention.")
                put(folder + "/media.mp4", "Synthetic nonempty file; playback tested separately.")
                fronts[item_id] = {"id": item_id, "platform": "instagram", "handle": uploader,
                                   "people_reviewed": True, "people": [{"id": "demo-speaker", "name": "Demo Speaker",
                                       "role": role, "evidence": "Explicit attribution in this synthetic fixture."}]}
                put(f"wiki/sources/instagram/{item_id}.md", doc(fronts[item_id], f"# Test {item_id}\n\nA synthetic source about attention."))
                rows.append(f"| {item_id} | {url} | reel | transcribed | {folder} |")
            rows.append("| Pending | https://www.instagram.com/p/Pending/ | post | discovered | |")
            catalog = json.loads((root / ".indexx.json").read_text())["paths"]["instagram_catalog_legacy"]
            put(catalog, "| shortcode | url | type | status | media_path |\n| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n")
            originals = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}

            def run(script, *args, success=True):
                result = subprocess.run([sys.executable, str(root / "scripts" / script), *args, "--root", str(root)],
                                        capture_output=True, text=True)
                if success:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return json.loads(result.stdout)
                self.assertNotEqual(result.returncode, 0)
                return result.stderr

            run("indexx_search.py", "build")
            found = run("indexx_search.py", "query", "--person", "D. Speaker", "--role", "speaker", "--type", "video", "--all")
            self.assertEqual([row["id"] for row in found["results"]], ["ClipA", "ClipB"])
            self.assertEqual(found["coverage"]["people_reviewed"], 3)
            self.assertEqual(found["coverage"]["unreviewed"], 1)
            view = run("indexx_watch.py", "--person", "Demo Speaker", "--role", "speaker", "--type", "video", "--name", "demo-speaker")
            self.assertEqual(view["count"], 2)
            self.assertEqual(Path(view["html_path"]).read_text().count("<video "), 2)
            self.assertEqual(Path(view["markdown_path"]).read_text().count("![[media/"), 2)
            self.assertTrue(run("indexx_search.py", "status")["fresh"])
            for path, before in originals.items():
                self.assertEqual(path.read_bytes(), before, str(path))
            fronts["ClipB"]["people"][0]["role"] = "mentioned"
            put("wiki/sources/instagram/ClipB.md", doc(fronts["ClipB"], "# Corrected fixture\n\nA mention, not a speaking appearance."))
            self.assertIn("stale", run("indexx_search.py", "query", success=False))
            run("indexx_search.py", "build")
            refreshed = run("indexx_search.py", "query", "--person", "Demo Speaker", "--role", "speaker", "--all")
            self.assertEqual([row["id"] for row in refreshed["results"]], ["ClipA"])


if __name__ == "__main__":
    unittest.main()
