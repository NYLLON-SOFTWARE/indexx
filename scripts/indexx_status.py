#!/usr/bin/env python3
"""Read-only, stdlib-only structural checks for an INDEXX library (Python 3.9+).

Audit validates rows claiming wiki_ingested; unfinished rows are counted, not failed.
--id ID --ready validates artifacts before changing that row to wiki_ingested.
This does not verify media decodability or the accuracy of transcriptions/summaries.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
from typing import Any, Optional
from urllib.parse import unquote, urlparse

STATUSES = {"discovered", "metadata", "downloaded", "transcribed", "wiki_ingested",
            "unavailable", "missing", "failed", "partial", "skipped_no_video"}
TERMINAL = {"unavailable", "skipped_no_video"}
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")
HANDLE_PATTERN = re.compile(r"[A-Za-z0-9_.]+\Z")
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PROVIDERS = {"grok": "grok_stt", "elevenlabs": "elevenlabs_scribe"}


class Invalid(ValueError):
    pass


def strict_json(text: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Invalid(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def bad_constant(value: str) -> None:
        raise Invalid(f"invalid JSON number: {value}")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise Invalid(str(exc)) from exc


def contained(base: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise Invalid("path must be a nonempty string")
    path = Path(raw).expanduser()
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise Invalid(f"path escapes {base}: {raw}") from exc
    return path


def nonempty(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise Invalid(f"missing or empty file: {path}")
    return path


def read_text(path: Path) -> str:
    text = nonempty(path).read_text(encoding="utf-8")
    if not text.strip():
        raise Invalid(f"empty text file: {path}")
    return text


def frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise Invalid("missing front matter (opening ---)")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise Invalid("unclosed front matter") from exc
    result: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_]*):[ \t]*(.+)", line)
        if not match:
            raise Invalid("front matter requires top-level key: value lines; use inline JSON for arrays/objects")
        key, value = match.groups()
        if key in result:
            raise Invalid(f"duplicate front matter key: {key}")
        if value[0] in '[{"' or value in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", value):
            result[key] = strict_json(value)
        else:
            # Deliberately accept only simple, unquoted YAML strings. No implicit dates/tags/aliases.
            if value.startswith(("'", "&", "*", "!", "|", ">")) or " #" in value:
                raise Invalid(f"unsupported scalar for {key}; use a JSON string")
            result[key] = value
    return result, "\n".join(lines[end + 1:])


def parse_catalog(text: str) -> list[dict[str, str]]:
    """One pipe table; escaped pipes stay in their cells. Never silently pad bad rows."""
    def cells(line: str) -> list[str]:
        return [v.strip().replace(r"\|", "|") for v in re.split(r"(?<!\\)\|", line.strip()[1:-1])]
    lines = text.splitlines()
    headers: Optional[list[str]] = None
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    separator_seen = False
    for line_no, line in enumerate(lines, 1):
        if line.strip().startswith("|") and line.strip().endswith(r"\|"):
            raise Invalid(f"catalog line {line_no}: table rows must end with an unescaped pipe")
        if not line.strip().startswith("|") or not line.strip().endswith("|"):
            if headers is not None and line.strip().startswith("|"):
                raise Invalid(f"catalog line {line_no}: table rows must end with a pipe")
            if headers is not None and line.strip():
                if any(other.strip().startswith("|") for other in lines[line_no:]):
                    raise Invalid("catalog rows must form one uninterrupted table")
                break
            continue
        cols = cells(line)
        if headers is None:
            if "shortcode" not in cols:
                continue
            headers = cols
            if len(set(headers)) != len(headers) or not {"shortcode", "url", "type", "status", "media_path"}.issubset(headers):
                raise Invalid("catalog needs unique shortcode/url/type/status/media_path columns")
            continue
        if not separator_seen:
            if len(cols) != len(headers) or not all(re.fullmatch(r":?-{3,}:?", v) for v in cols):
                raise Invalid(f"catalog line {line_no}: missing table separator")
            separator_seen = True
            continue
        if len(cols) != len(headers):
            raise Invalid(f"catalog line {line_no}: expected {len(headers)} cells, found {len(cols)}")
        row = dict(zip(headers, cols))
        item_id, platform = row["shortcode"], row.get("platform", "instagram")
        if not ID_PATTERN.fullmatch(item_id) or platform != "instagram":
            raise Invalid(f"catalog line {line_no}: invalid Instagram shortcode/platform")
        if row["status"] not in STATUSES:
            raise Invalid(f"catalog line {line_no}: unknown status {row['status']!r}")
        key = (platform, item_id)
        if key in seen:
            raise Invalid(f"duplicate (platform, id): {platform}/{item_id}")
        seen.add(key)
        rows.append(row)
    if headers is None or not separator_seen:
        raise Invalid("catalog has no valid shortcode table")
    return rows


def load_catalog(root: Path) -> tuple[dict[str, Any], Path, list[dict[str, str]]]:
    cfg = strict_json(read_text(root / ".indexx.json"))
    if not isinstance(cfg, dict) or not isinstance(cfg.get("paths"), dict):
        raise Invalid(".indexx.json requires a paths object")
    paths = cfg["paths"]
    use = paths.get("use_catalog")
    if use not in ("legacy", "catalog"):
        raise Invalid("paths.use_catalog must be legacy or catalog")
    key = "instagram_catalog_legacy" if use == "legacy" else "instagram_catalog"
    catalog = contained(root, paths.get(key))
    return cfg, catalog, parse_catalog(read_text(catalog))


def person_page(root: Path, slug: str) -> dict[str, Any]:
    """Read an explicit person identity; names are never inferred from media."""
    if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
        raise Invalid("person id must be a kebab-case slug")
    path = contained(root, f"wiki/entities/people/{slug}.md")
    front, body = frontmatter(read_text(path))
    if front.get("id") != slug:
        raise Invalid(f"person page id must match filename: {slug}")
    name, aliases = front.get("name"), front.get("aliases", [])
    if not isinstance(name, str) or not name.strip():
        raise Invalid(f"person page needs a name: {slug}")
    if (not isinstance(aliases, list)
            or not all(isinstance(a, str) and a.strip() for a in aliases)
            or len({a.strip().casefold() for a in aliases}) != len(aliases)):
        raise Invalid(f"person aliases must be distinct nonempty strings: {slug}")
    if not re.sub(r"^#{1,6}[^\n]*", "", body, flags=re.M).strip():
        raise Invalid(f"person page needs a cited body: {slug}")
    return {"id": slug, "name": name.strip(), "aliases": [a.strip() for a in aliases], "body": body}


def person_annotations(front: dict[str, Any], root: Path) -> list[dict[str, str]]:
    """Validate optional source annotations without invalidating older libraries.

    Evidence is a source-grounded explanation, not proof of correct attribution.
    The ingest/lint content review must check it against the cited source.
    """
    reviewed = front.get("people_reviewed", False)
    if not isinstance(reviewed, bool):
        raise Invalid("people_reviewed must be a boolean")
    if reviewed and "people" not in front:
        raise Invalid("people_reviewed requires an explicit people list (possibly empty)")
    people = front.get("people", [])
    if not isinstance(people, list):
        raise Invalid("people must be an inline JSON array")
    seen = set()
    result = []
    for person in people:
        if not isinstance(person, dict) or set(person) != {"id", "name", "role", "evidence"}:
            raise Invalid("each person needs exactly id, name, role, and evidence")
        if not all(isinstance(person[key], str) and person[key].strip() for key in person):
            raise Invalid("person id/name/role/evidence must be nonempty strings")
        if person["role"] not in ("speaker", "featured", "mentioned"):
            raise Invalid("person role must be speaker, featured, or mentioned")
        key = (person["id"], person["role"])
        if key in seen:
            raise Invalid("duplicate person id/role")
        seen.add(key)
        page = person_page(root, person["id"])
        if person["name"].strip().casefold() != page["name"].casefold():
            raise Invalid(f"person name does not match canonical page: {person['id']}")
        item_id = front.get("id")
        if isinstance(item_id, str) and ID_PATTERN.fullmatch(item_id):
            # Require an actual local link, not a pathname mentioned in prose.
            target = f"sources/instagram/{item_id}"
            wiki_targets = [value.split("|", 1)[0].split("#", 1)[0].strip()
                            for value in re.findall(r"\[\[([^\]\n]+)\]\]", page["body"])]
            linked = any(value in (target, target + ".md", "wiki/" + target, "wiki/" + target + ".md")
                         for value in wiki_targets)
            parent = root / "wiki/entities/people"
            expected = (root / "wiki" / (target + ".md")).resolve()
            for value in re.findall(r"\[[^\]\n]*\]\(<?([^\s)>]+)>?\)", page["body"]):
                parsed = urlparse(value)
                if parsed.scheme or parsed.netloc:
                    continue
                if (parent / unquote(parsed.path)).resolve() == expected:
                    linked = True
            if not linked:
                raise Invalid(f"person page must link source {item_id}: {person['id']}")
        result.append(dict(person))
    return result


def classification(front: dict[str, Any]) -> None:
    tags, facets = front.get("tags"), front.get("facets")
    if (not isinstance(tags, list) or not 5 <= len(tags) <= 10
            or not all(isinstance(t, str) and SLUG_PATTERN.fullmatch(t) for t in tags)
            or len(set(tags)) != len(tags)):
        raise Invalid("tags must contain 5–10 distinct kebab-case strings")
    if not isinstance(facets, dict) or set(facets) != {"form", "topic", "intent"}:
        raise Invalid("facets must contain exactly form, topic, and intent")
    form, topic, intent = facets["form"], facets["topic"], facets["intent"]
    if not isinstance(form, str) or not SLUG_PATTERN.fullmatch(form):
        raise Invalid("facets.form must be one kebab-case string")
    if (not isinstance(topic, list) or not 1 <= len(topic) <= 3
            or not all(isinstance(t, str) and SLUG_PATTERN.fullmatch(t) for t in topic)
            or len(set(topic)) != len(topic)):
        raise Invalid("facets.topic must contain 1–3 distinct kebab-case strings")
    if intent not in ("entertainment", "inspiration", "reference", "learn"):
        raise Invalid("facets.intent must be one allowed intent")


def instagram_id(url: Any) -> Optional[str]:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    match = re.fullmatch(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc not in ("instagram.com", "www.instagram.com") or not match:
        return None
    return match.group(1)


def sources_links(body: str, item: Path, required: list[Path]) -> None:
    match = re.search(r"^#{1,6}\s+Sources\s*\n(.*?)(?=^#{1,6}\s|\Z)", body, re.M | re.S)
    if not match:
        raise Invalid("transcript needs a Sources heading")
    targets = set()
    for raw in re.findall(r"\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))\)", match.group(1)):
        value = unquote(raw[0] or raw[1])
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            continue
        targets.add(contained(item, parsed.path))
    if not set(required).issubset(targets):
        raise Invalid("transcript Sources must link the local media and audio files")


def number(value: Any) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def words_check(path: Path, duration: Optional[float]) -> None:
    words = strict_json(read_text(path))
    if not isinstance(words, list) or not words:
        raise Invalid("transcript.words.json must be a nonempty normalized word array")
    previous = -1.0
    for n, word in enumerate(words, 1):
        if not isinstance(word, dict) or not {"text", "start", "end"}.issubset(word) or set(word) - {"text", "start", "end", "speaker"}:
            raise Invalid(f"word {n}: expected text/start/end and optional speaker")
        start, end = word["start"], word["end"]
        if (not isinstance(word["text"], str) or not word["text"].strip()
                or not number(start) or not number(end) or start < 0 or end <= start or start < previous):
            raise Invalid(f"word {n}: invalid text or timestamps")
        if "speaker" in word and (not isinstance(word["speaker"], str) or not word["speaker"].strip()):
            raise Invalid(f"word {n}: speaker must be a nonempty string")
        if duration is not None and end > duration + 0.5:
            raise Invalid(f"word {n}: end exceeds media duration")
        previous = start


def vtt_check(path: Path, duration: Optional[float]) -> None:
    text = read_text(path).replace("\r\n", "\n")
    blocks = re.split(r"\n[ \t]*\n", text.strip())
    if blocks[0] != "WEBVTT":
        raise Invalid("transcript.vtt must start with WEBVTT and a blank line")
    stamp = r"(?:(\d{2,}):)?([0-5]\d):([0-5]\d)\.(\d{3})"
    def seconds(value: str) -> float:
        match = re.fullmatch(stamp, value)
        if not match:
            raise Invalid(f"invalid VTT timestamp: {value}")
        h, m, s, ms = match.groups()
        return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    previous = -1.0
    cues = 0
    for block in blocks[1:]:
        lines = block.splitlines()
        if not lines:
            continue
        # Normalized output supports optional cue identifiers, no styling/settings/metadata.
        idx = 0 if " --> " in lines[0] else 1
        if len(lines) <= idx + 1 or lines[idx].count(" --> ") != 1:
            raise Invalid("VTT cue needs a timestamp line and nonempty text")
        start, end = map(seconds, lines[idx].split(" --> "))
        if start < previous or end <= start or not "\n".join(lines[idx + 1:]).strip():
            raise Invalid("VTT cue has invalid order/duration/text")
        if duration is not None and end > duration + 0.5:
            raise Invalid("VTT cue exceeds media duration")
        previous, cues = start, cues + 1
    if not cues:
        raise Invalid("transcript.vtt contains no cues")


def validate_item(root: Path, row: dict[str, str]) -> list[str]:
    """Fail closed per item; no writes. Return actionable first structural failure."""
    try:
        item_id = row["shortcode"]
        if instagram_id(row["url"]) != item_id:
            raise Invalid("catalog URL does not identify the Instagram shortcode")
        media_root = contained(root, "media/instagram")
        media_path = contained(root, row["media_path"])
        item = media_path.parent if media_path.is_file() else media_path
        try:
            item.relative_to(media_root)
        except ValueError as exc:
            raise Invalid("media_path must be an item folder/file under media/instagram") from exc
        info = strict_json(read_text(contained(item, "info.json")))
        if not isinstance(info, dict):
            raise Invalid("info.json must be an object")
        if info.get("id", info.get("shortcode")) != item_id or info.get("platform") != "instagram":
            raise Invalid("info.json platform/id does not match catalog")
        if instagram_id(info.get("source_url", info.get("url"))) != item_id:
            raise Invalid("info.json source_url does not match catalog")
        handle, kind, speech = info.get("handle"), info.get("type"), info.get("transcript_status")
        if not isinstance(handle, str) or not HANDLE_PATTERN.fullmatch(handle) or handle in (".", ".."):
            raise Invalid("info.json handle must be an Instagram handle without @")
        if row.get("handle") and row["handle"].lstrip("@") != handle:
            raise Invalid("info.json handle does not match catalog")
        if kind not in ("video", "image", "carousel"):
            raise Invalid("info.json type must be video, image, or image-only carousel")
        if row["type"] not in {"video": ("video", "reel", "post"), "image": ("image", "post"), "carousel": ("carousel",)}[kind]:
            raise Invalid("info.json type does not match catalog")
        duration = info.get("duration_seconds")
        if duration is not None and (not number(duration) or duration <= 0):
            raise Invalid("info.json duration_seconds must be positive and finite")
        source_path = contained(root, f"wiki/sources/instagram/{item_id}.md")
        source_front, source_body = frontmatter(read_text(source_path))
        if not source_body.strip():
            raise Invalid("wiki source page has no body")
        for field, value in (("id", item_id), ("platform", "instagram"), ("handle", handle)):
            if source_front.get(field) != value:
                raise Invalid(f"wiki source front matter {field} does not match info.json")
        classification(source_front)
        person_annotations(source_front, root)
        read_text(contained(root, f"wiki/entities/creators/{handle}.md"))
        if kind in ("image", "carousel"):
            if speech != "not_applicable":
                raise Invalid("image-only items require transcript_status: not_applicable")
            images = info.get("image_files")
            if not isinstance(images, list) or not images or not all(isinstance(p, str) for p in images):
                raise Invalid("image-only items require image_files")
            if kind == "image" and len(images) != 1:
                raise Invalid("image items require exactly one image file")
            if len(set(images)) != len(images):
                raise Invalid("image_files contains duplicates")
            for raw in images:
                if Path(raw).suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif"):
                    raise Invalid("image_files must name image files")
                nonempty(contained(item, raw))
            return []
        media = nonempty(contained(item, "media.mp4"))
        audio = contained(item, "audio.mp3")
        if not audio.exists():
            audio = contained(item, "audio.wav")
        nonempty(audio)
        front, body = frontmatter(read_text(contained(item, "transcript.md")))
        if not body.strip():
            raise Invalid("transcript has no body")
        classification(front)
        if any(front[field] != source_front[field] for field in ("tags", "facets")):
            raise Invalid("transcript and wiki source tags/facets must agree")
        if front.get("media") != media.name or front.get("audio") != audio.name:
            raise Invalid("transcript media/audio front matter must name the local files")
        if front.get("transcript_status") != speech or speech not in ("speech", "no_speech"):
            raise Invalid("video transcript_status must agree in info.json and transcript.md")
        sources_links(body, item, [media, audio])
        narrative = re.split(r"^#{1,6}\s+Sources\s*$", body, maxsplit=1, flags=re.M)[0]
        if not re.sub(r"[#\s]", "", narrative):
            raise Invalid("transcript needs readable text or an explicit no-speech note before Sources")
        if speech == "no_speech":
            reason = info.get("no_speech_reason")
            if not isinstance(reason, str) or not reason.strip() or front.get("no_speech_reason") != reason:
                raise Invalid("no-speech items require matching nonempty no_speech_reason metadata")
            if not re.search(r"\bno[- ]speech\b", narrative, re.I):
                raise Invalid("transcript must explicitly state no speech")
        # STT provenance is historical: changing the configured provider must not invalidate old transcripts.
        stt = info.get("stt")
        if stt is not None:
            if not isinstance(stt, dict) or stt.get("provider") not in PROVIDERS:
                raise Invalid("info.json stt requires provider and model")
            if front.get("source") != PROVIDERS[stt["provider"]] or front.get("model") != stt.get("model"):
                raise Invalid("transcript source/model does not match info.json stt provenance")
        if speech == "speech" or front.get("source") in PROVIDERS.values():
            if front.get("source") not in PROVIDERS.values():
                raise Invalid("transcript source must identify the actual STT provider")
            model = front.get("model")
            if not isinstance(model, str) or not model.strip():
                raise Invalid("transcript model must record the actual STT model")
            if front["source"] == "grok_stt" and model not in ("grok-voice-transcribe-1.0", "grok-voice-transcribe-2.0"):
                raise Invalid("unsupported historical Grok model; preserve its provenance and review the schema")
        elif front.get("source") != "visual_triage" or "model" in front:
            raise Invalid("no-speech without STT requires source: visual_triage and no STT model claim")
        if speech == "speech":
            words_check(contained(item, "transcript.words.json"), duration)
            vtt_check(contained(item, "transcript.vtt"), duration)
        return []
    except (Invalid, OSError, UnicodeError, TypeError, ValueError, RuntimeError) as exc:
        return [str(exc)]


def audit(root: Path, item_id: Optional[str] = None, ready: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"root": str(root), "catalog": None, "total": 0, "status_counts": {},
                              "backlog": 0, "terminal_excluded": 0, "claimed_complete": 0,
                              "fully_processed": 0, "invalid_complete": 0,
                              "ready": None, "errors": [], "items": []}
    try:
        _, path, rows = load_catalog(root)
        result["catalog"] = str(path)
        counts = Counter(row["status"] for row in rows)
        result.update(total=len(rows), status_counts=dict(sorted(counts.items())),
                      backlog=sum(n for s, n in counts.items() if s not in TERMINAL | {"wiki_ingested"}),
                      terminal_excluded=sum(counts[s] for s in TERMINAL), claimed_complete=counts["wiki_ingested"])
        selected = [row for row in rows if item_id is None or row["shortcode"] == item_id]
        if item_id is not None and not selected:
            raise Invalid(f"shortcode not found: {item_id}")
        for row in rows:
            should_check = row["status"] == "wiki_ingested" or (item_id is not None and row in selected)
            if not should_check:
                continue
            errors = validate_item(root, row)
            if item_id is not None and row in selected and not ready and row["status"] != "wiki_ingested":
                errors.insert(0, "item is not wiki_ingested; use --ready to check pre-completion artifacts")
            if ready and row in selected and row["status"] in TERMINAL:
                errors.insert(0, "excluded terminal status cannot be marked wiki_ingested; resolve status first")
            valid = not errors
            result["items"].append({"id": row["shortcode"], "status": row["status"], "valid": valid, "errors": errors})
            if row["status"] == "wiki_ingested":
                result["fully_processed" if valid else "invalid_complete"] += 1
            if ready and row in selected:
                result["ready"] = valid
        # A selected readiness check concerns that item; whole-library audits still reveal all corrupt claims.
        failing = [item for item in result["items"] if not item["valid"] and (item_id is None or item["id"] == item_id)]
        result["ok"] = not failing
    except (Invalid, OSError, UnicodeError, TypeError, ValueError, RuntimeError) as exc:
        result["errors"].append(str(exc))
        result["ok"] = False
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Library root (default: current directory)")
    parser.add_argument("--id", dest="item_id", help="Instagram shortcode to check")
    parser.add_argument("--ready", action="store_true", help="Check artifacts before marking the selected item wiki_ingested")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args(argv)
    if args.ready and not args.item_id:
        parser.error("--ready requires --id")
    result = audit(Path(args.root).expanduser().resolve(), args.item_id, args.ready)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"INDEXX status — {result['root']}")
        for key in ("total", "claimed_complete", "fully_processed", "invalid_complete", "backlog", "terminal_excluded"):
            print(f"{key}: {result[key]}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for item in result["items"]:
            print(f"{item['id']}: {'valid' if item['valid'] else 'INVALID'} ({item['status']})")
            for error in item["errors"]:
                print(f"  {error}")
        if args.ready:
            print(f"ready: {result['ready']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
