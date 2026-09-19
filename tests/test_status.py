"""Fixture tests for completion claims, readiness, and safe local path handling."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from indexx_status import audit, parse_catalog, Invalid
from indexx_dashboard import gather


class StatusTests(unittest.TestCase):
    def test_escaped_final_pipe_cannot_terminate_catalog_row(self):
        malformed = ("| shortcode | url | type | status | media_path |\n"
                     "| --- | --- | --- | --- | --- |\n"
                     "| Example123 | https://www.instagram.com/p/Example123/ | reel | discovered | literal\\|\n")
        with self.assertRaisesRegex(Invalid, "unescaped pipe"):
            parse_catalog(malformed)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.item = self.root / "media/instagram/example_creator/2026-09-19_Example123"
        self.item.mkdir(parents=True)
        self.config = {"root": str(self.root), "stt": {"provider": "grok"}, "paths": {
            "use_catalog": "catalog", "instagram_catalog": "catalog/custom.md"}}
        self.info = {"id": "Example123", "platform": "instagram", "handle": "example_creator",
                     "type": "video", "source_url": "https://www.instagram.com/reel/Example123/",
                     "duration_seconds": 3, "transcript_status": "speech",
                     "stt": {"provider": "grok", "model": "grok-voice-transcribe-2.0"}}
        self.tags = ["learning", "focus", "practice", "reflection", "habits"]
        self.facets = {"form": "talk", "topic": ["learning"], "intent": "learn"}
        self.front = {"media": "media.mp4", "audio": "audio.mp3", "source": "grok_stt",
                      "model": "grok-voice-transcribe-2.0", "transcript_status": "speech",
                      "tags": self.tags, "facets": self.facets}
        self.source_front = {"id": "Example123", "platform": "instagram", "handle": "example_creator",
                             "tags": self.tags, "facets": self.facets}
        self.write_json(self.root / ".indexx.json", self.config)
        self.catalog()
        self.save_info()
        for name in ("media.mp4", "audio.mp3"):
            # Deliberately synthetic: this checker verifies structure, not playable media.
            (self.item / name).write_bytes(b"nonempty-fixture")
        self.transcript()
        self.source()
        creator = self.root / "wiki/entities/creators/example_creator.md"
        creator.parent.mkdir(parents=True)
        creator.write_text("# Creator\n\n[[sources/instagram/Example123]]\n")
        self.write_json(self.item / "transcript.words.json", [
            {"text": "Hello", "start": 0.1, "end": 0.5},
            {"text": "world", "start": 0.5, "end": 1.2, "speaker": "speaker-1"}])
        (self.item / "transcript.vtt").write_text("WEBVTT\n\n00:00.100 --> 00:01.200\nHello world\n")

    def write_json(self, path, value):
        path.write_text(json.dumps(value) + "\n")

    def save_info(self):
        self.write_json(self.item / "info.json", self.info)

    def catalog(self, status="wiki_ingested", extra="", media_path=None, kind="reel"):
        path = self.root / "catalog/custom.md"
        path.parent.mkdir(exist_ok=True)
        relative = media_path or str(self.item.relative_to(self.root))
        path.write_text("| shortcode | url | type | status | media_path |\n"
                        "| --- | --- | --- | --- | --- |\n"
                        f"| Example123 | https://www.instagram.com/reel/Example123/ | {kind} | {status} | {relative} |\n" + extra)

    def document(self, front, body):
        return "---\n" + "\n".join(f"{key}: {json.dumps(value)}" for key, value in front.items()) + "\n---\n" + body

    def transcript(self, body=None):
        body = body or "Hello world.\n\n## Sources\n- [Video](media.mp4)\n- [Audio](audio.mp3)\n"
        (self.item / "transcript.md").write_text(self.document(self.front, body))

    def source(self):
        path = self.root / "wiki/sources/instagram/Example123.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.document(self.source_front, "# Example\n\nSupported summary. [Original](https://www.instagram.com/reel/Example123/)\n"))

    def check_invalid(self, contains):
        result = audit(self.root)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["fully_processed"], 0)
        errors = result["errors"] + [message for item in result["items"] for message in item["errors"]]
        self.assertIn(contains, " ".join(errors))

    def test_complete_item_and_backlog_are_counted_separately(self):
        self.catalog(extra="| Pending | https://www.instagram.com/p/Pending/ | image | discovered | |\n"
                           "| Deleted | https://www.instagram.com/p/Deleted/ | image | unavailable | |\n")
        result = audit(self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["total"], result["fully_processed"], result["backlog"], result["terminal_excluded"]), (3, 1, 1, 1))

    def test_readiness_has_no_circular_status_requirement(self):
        self.catalog(status="transcribed")
        ready = audit(self.root, "Example123", ready=True)
        self.assertTrue(ready["ready"], ready)
        self.assertTrue(ready["ok"])
        self.assertEqual(ready["fully_processed"], 0)
        self.assertFalse(audit(self.root, "Example123")["ok"])

    def test_backlog_missing_artifacts_does_not_fail_full_audit(self):
        self.catalog(status="discovered")
        (self.item / "media.mp4").unlink()
        self.assertTrue(audit(self.root)["ok"])
        self.assertFalse(audit(self.root, "Example123", ready=True)["ok"])

    def test_terminal_excluded_cannot_be_silently_readied(self):
        self.catalog(status="skipped_no_video")
        result = audit(self.root, "Example123", ready=True)
        self.assertFalse(result["ready"])
        self.assertIn("excluded terminal status", result["items"][0]["errors"][0])

    def test_required_files_missing_or_empty(self):
        for relative in ("media.mp4", "audio.mp3", "info.json", "transcript.md", "transcript.vtt", "transcript.words.json"):
            with self.subTest(relative=relative):
                path = self.item / relative
                saved = path.read_bytes()
                path.write_bytes(b"")
                self.check_invalid("missing or empty file")
                path.write_bytes(saved)

    def test_word_timestamp_constraints(self):
        bad = [
            [{"text": "Hello", "start": -1, "end": 0.2}],
            [{"text": "Hello", "start": 1, "end": 0.2}],
            [{"text": "Hello", "start": True, "end": 2}],
            [{"text": "Hello", "start": 0, "end": float("nan")}],
            [{"text": "Hello", "start": 0, "end": 12}],
            [{"text": "Hello", "start": 1, "end": 2}, {"text": "world", "start": 0, "end": 1}],
        ]
        for words in bad:
            with self.subTest(words=words):
                self.write_json(self.item / "transcript.words.json", words)
                self.assertFalse(audit(self.root)["ok"])

    def test_vtt_malformed_or_reversed(self):
        for vtt in ("not VTT", "WEBVTT\n\n00:61.000 --> 00:62.000\nBad\n",
                    "WEBVTT\n\n00:02.000 --> 00:01.000\nBad\n", "WEBVTT\n\n"):
            with self.subTest(vtt=vtt):
                (self.item / "transcript.vtt").write_text(vtt)
                self.assertFalse(audit(self.root)["ok"])

    def test_missing_sources_and_false_frontmatter_paths(self):
        self.transcript("Hello world.\n")
        self.check_invalid("Sources heading")
        self.transcript("Hello.\n\n## Sources\n- [Video](media.mp4)\n- [Wrong](transcript.md)\n")
        self.check_invalid("must link the local media and audio")

    def test_provider_provenance_mismatch_fails_but_preference_switch_is_safe(self):
        self.config["stt"]["provider"] = "elevenlabs"
        self.write_json(self.root / ".indexx.json", self.config)
        self.assertTrue(audit(self.root)["ok"])
        self.info["stt"] = {"provider": "elevenlabs", "model": "scribe_v2"}
        self.save_info()
        self.check_invalid("does not match info.json stt")

    def test_legacy_optional_info_provenance(self):
        del self.info["stt"]
        self.save_info()
        self.assertTrue(audit(self.root)["ok"])
        del self.front["model"]
        self.transcript()
        self.check_invalid("actual STT model")

    def test_historical_grok_1_preserves_truthful_provenance(self):
        self.front["model"] = "grok-voice-transcribe-1.0"
        self.info["stt"]["model"] = "grok-voice-transcribe-1.0"
        self.transcript()
        self.save_info()
        self.assertTrue(audit(self.root)["ok"])
        self.assertEqual(json.loads((self.item / "info.json").read_text())["stt"]["model"], "grok-voice-transcribe-1.0")
        self.info["stt"]["model"] = "grok-voice-transcribe-2.0"
        self.save_info()
        self.check_invalid("does not match info.json stt")

    def test_normalized_elevenlabs_words_pass_but_raw_provider_records_fail(self):
        self.front.update(source="elevenlabs_scribe", model="scribe_v2")
        self.info["stt"] = {"provider": "elevenlabs", "model": "scribe_v2"}
        self.transcript()
        self.save_info()
        self.write_json(self.item / "transcript.words.json", [
            {"text": "Hello", "start": 0.12, "end": 0.48, "speaker": "speaker_0"}])
        self.assertTrue(audit(self.root)["ok"])
        self.write_json(self.item / "transcript.words.json", [
            {"text": "Hello", "start": 0.12, "end": 0.48, "type": "word", "speaker_id": "speaker_0"}])
        self.check_invalid("expected text/start/end and optional speaker")

    def test_no_speech_needs_explicit_evidence(self):
        self.info.update(transcript_status="no_speech", no_speech_reason="Reviewed music-only audio")
        del self.info["stt"]
        self.save_info()
        self.front.update(transcript_status="no_speech", source="visual_triage", no_speech_reason=self.info["no_speech_reason"])
        del self.front["model"]
        for name in ("transcript.words.json", "transcript.vtt"):
            (self.item / name).unlink()
        self.transcript("No speech: reviewed music-only audio.\n\n## Sources\n- [Video](media.mp4)\n- [Audio](audio.mp3)\n")
        self.assertTrue(audit(self.root)["ok"])
        self.info.pop("no_speech_reason")
        self.save_info()
        self.check_invalid("no_speech_reason")

    def test_image_only_can_complete_without_fake_transcript(self):
        for child in self.item.iterdir():
            child.unlink()
        self.info.update(type="image", transcript_status="not_applicable", image_files=["image-01.jpg"])
        self.info.pop("stt")
        self.save_info()
        (self.item / "image-01.jpg").write_bytes(b"image-fixture")
        self.catalog(kind="image")
        self.assertTrue(audit(self.root)["ok"])
        (self.item / "image-01.jpg").unlink()
        self.check_invalid("missing or empty file")

    def test_classification_and_source_identity(self):
        self.source_front["tags"] = ["only-one"]
        self.source()
        self.check_invalid("5–10")
        self.source_front["tags"] = self.tags
        self.source_front["facets"] = {"form": "talk", "topic": [], "intent": "learn"}
        self.source()
        self.check_invalid("1–3")
        self.source_front["facets"] = self.facets
        self.source_front["id"] = "OtherId"
        self.source()
        self.check_invalid("id does not match")

    def test_creator_required(self):
        (self.root / "wiki/entities/creators/example_creator.md").unlink()
        self.check_invalid("missing or empty file")

    def test_stale_frontmatter_is_reported_without_mutation(self):
        original = "---\ntags:\n  - example\n---\nOld content.\n"
        (self.item / "transcript.md").write_text(original)
        self.check_invalid("front matter requires")
        self.assertEqual((self.item / "transcript.md").read_text(), original)

    def test_catalog_duplicate_ids_and_malformed_rows(self):
        row = (self.root / "catalog/custom.md").read_text().splitlines()[-1]
        self.catalog(extra=row + "\n")
        self.check_invalid("duplicate (platform, id)")
        self.catalog(extra="| Broken | wiki_ingested |\n")
        self.check_invalid("expected 5 cells")
        self.catalog(extra="| Broken | wiki_ingested\n")
        self.check_invalid("must end with a pipe")
        self.catalog(extra="interruption\n" + row + "\n")
        self.check_invalid("one uninterrupted table")

    def test_missing_or_invalid_config_does_not_fall_back(self):
        path = self.root / ".indexx.json"
        path.unlink()
        self.check_invalid("missing or empty file")
        for value in ([], {"paths": {}}, {"paths": {"use_catalog": "guess"}}):
            with self.subTest(value=value):
                self.write_json(path, value)
                self.assertFalse(audit(self.root)["ok"])
        path.write_text('{"paths":{},"paths":{}}')
        self.check_invalid("duplicate JSON key")

    def test_outside_paths_and_symlinks_fail(self):
        self.catalog(media_path="../external")
        self.check_invalid("path escapes")
        self.catalog()
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "audio.mp3"
            path.write_bytes(b"audio")
            (self.item / "audio.mp3").unlink()
            (self.item / "audio.mp3").symlink_to(path)
            self.check_invalid("path escapes")
        self.config["paths"]["instagram_catalog"] = "../external.md"
        self.write_json(self.root / ".indexx.json", self.config)
        self.check_invalid("path escapes")

    def test_dashboard_never_uses_claimed_status_as_verified_count(self):
        self.assertEqual(gather(self.root)["fully_processed"]["count"], 1)
        (self.item / "media.mp4").unlink()
        data = gather(self.root)
        self.assertEqual(data["catalog"]["by_status"]["wiki_ingested"], 1)
        self.assertEqual(data["fully_processed"]["count"], 0)
        self.assertTrue(any("fail structural validation" in gap for gap in data["gaps"]))
        (self.root / ".indexx.json").unlink()
        self.assertIsNone(gather(self.root)["fully_processed"]["count"])

    def test_dashboard_labels_use_local_timezone(self):
        local_time = datetime(2026, 9, 19, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30), "IST"))
        with patch("indexx_dashboard.now_local", return_value=local_time):
            data = gather(self.root)
        self.assertEqual(data["generated_at"], "2026-09-19T12:30:00+05:30")
        self.assertTrue(data["generated_at_label"].endswith("IST"))

    def test_cli_json_and_shell_wrapper_exit_status(self):
        cmd = [sys.executable, str(SCRIPTS / "indexx_status.py"), "--root", str(self.root), "--json"]
        good = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["fully_processed"], 1)
        (self.item / "info.json").write_text("{}")
        failed = subprocess.run(["bash", str(SCRIPTS / "indexx-status.sh"), str(self.root), "--json"], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout)["invalid_complete"], 1)

    def test_unknown_selected_id_and_ready_without_id(self):
        self.assertFalse(audit(self.root, "DoesNotExist", ready=True)["ok"])
        proc = subprocess.run([sys.executable, str(SCRIPTS / "indexx_status.py"), "--ready"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--ready requires --id", proc.stderr)


if __name__ == "__main__":
    unittest.main()
