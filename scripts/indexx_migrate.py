#!/usr/bin/env python3
"""Plan a legacy library format migration; --apply opts in after local backups.

This updates only the selected catalog and, when needed, its provider setting.
It never downloads content or verifies that completed items are actually complete.
Run from the reviewed source checkout, with no other library writer running.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Optional

from indexx_status import ID_PATTERN, Invalid, STATUSES, instagram_id, parse_catalog, strict_json


# These paths belong to support, runtime state, or artifacts, not a catalog.
RESERVED_FILES = {".indexx.json", "AGENTS.md", "SCHEMA.md", "README.md", ".gitignore"}
RESERVED_TREES = {"scripts", "logs", "media", "wiki", ".git", ".codex", ".agents"}
LIBRARY_DIRECTORIES = {"catalog", "markdown", "markdown/instagram"} | RESERVED_TREES


def safe_path(root: Path, raw: str) -> Path:
    """Reject redirects, including in-root symlinks that alias a different target."""
    if not isinstance(raw, str) or not raw.strip():
        raise Invalid("Expected a nonempty library path")
    given = Path(raw).expanduser()
    path = given if given.is_absolute() else root / given
    if ".." in given.parts:
        raise Invalid(f"Parent traversal is not allowed: {raw}")
    try:
        relative = path.relative_to(root)
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise Invalid(f"Path escapes the library: {raw}") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise Invalid(f"Symlink paths are not migrated: {current}")
        if current != path and current.exists() and not current.is_dir():
            raise Invalid(f"Expected a directory: {current}")
    return path


def read_object(path: Path) -> dict:
    value = strict_json(path.read_bytes().decode("utf-8"))
    if not isinstance(value, dict):
        raise Invalid(f"Expected a JSON object: {path}")
    return value


def provider_config(config: dict, provider: Optional[str]) -> tuple[dict, bool]:
    if provider not in (None, "grok", "elevenlabs"):
        raise Invalid("Provider must be grok or elevenlabs")
    stt = config.get("stt")
    if not isinstance(stt, dict):
        if provider is None:
            raise Invalid("Legacy or missing stt settings require explicit --provider grok|elevenlabs")
        stt = {}
    chosen = stt.get("provider")
    if chosen in ("grok", "elevenlabs") and provider is not None and provider != chosen:
        raise Invalid("Migration cannot switch an existing valid provider selection")
    legacy = "primary" in stt or "fallback" in stt or "provider" not in stt or chosen not in (None, "grok", "elevenlabs")
    if legacy and provider is None and chosen not in ("grok", "elevenlabs"):
        raise Invalid("Legacy provider/primary/fallback settings require explicit --provider grok|elevenlabs; no selection is inferred")
    updated = dict(stt)
    if provider is not None:
        updated["provider"] = provider
    # A canonical selection already records the user's choice. Obsolete defaults
    # cannot override it or require the same choice again; backups preserve them.
    if provider is not None or chosen in ("grok", "elevenlabs"):
        updated.pop("primary", None)
        updated.pop("fallback", None)
    result = dict(config)
    result["stt"] = updated
    return result, result != config


def split_table_line(line: str) -> tuple[str, list[str], str]:
    # Match the current status parser's delimiter rule, including at the edges.
    # A final escaped pipe belongs to a cell and cannot terminate the row.
    delimiters = list(re.finditer(r"(?<!\\)\|", line))
    if len(delimiters) < 2:
        raise Invalid("Catalog table rows must start and end with an unescaped pipe")
    first, last = delimiters[0].start(), delimiters[-1].start()
    if line[:first].strip() or line[last + 1:].strip():
        raise Invalid("Catalog table rows must start and end with an unescaped pipe")
    return line[:first], re.split(r"(?<!\\)\|", line[first + 1:last]), line[last + 1:]


def cell_value(raw: str) -> str:
    return raw.strip().replace(r"\|", "|")


def legacy_table(text: str) -> tuple[list[str], list[str], int, int, list[tuple[int, list[str], dict]]]:
    lines = text.splitlines(keepends=True)
    header_idx = None
    for number, line in enumerate(lines):
        if line.strip().startswith("|"):
            _, raw, _ = split_table_line(line)
            if {"shortcode", "url", "type", "status"}.issubset(map(cell_value, raw)):
                header_idx = number
                break
    if header_idx is None:
        raise Invalid("Catalog has no shortcode table")
    _, raw_headers, _ = split_table_line(lines[header_idx])
    headers = [cell_value(v) for v in raw_headers]
    if len(set(headers)) != len(headers) or not {"shortcode", "url", "type", "status"}.issubset(headers):
        raise Invalid("Catalog needs unique shortcode/url/type/status columns")
    separator_idx = header_idx + 1
    if separator_idx >= len(lines):
        raise Invalid("Catalog is missing its table separator")
    _, separator, _ = split_table_line(lines[separator_idx])
    if len(separator) != len(headers) or not all(re.fullmatch(r":?-{3,}:?", v.strip()) for v in separator):
        raise Invalid("Catalog is missing a valid table separator")
    rows = []
    seen = set()
    ended = False
    for number in range(separator_idx + 1, len(lines)):
        line = lines[number]
        if not line.strip():
            continue
        if not line.strip().startswith("|"):
            ended = True
            continue
        if ended:
            raise Invalid("Catalog rows must form one uninterrupted table")
        _, raw, _ = split_table_line(line)
        if len(raw) != len(headers):
            raise Invalid(f"Catalog line {number + 1}: expected {len(headers)} cells, found {len(raw)}")
        row = dict(zip(headers, map(cell_value, raw)))
        item_id, platform = row["shortcode"], row.get("platform", "instagram")
        if not ID_PATTERN.fullmatch(item_id) or platform != "instagram":
            raise Invalid(f"Invalid Instagram identity on catalog line {number + 1}")
        if instagram_id(row["url"]) != item_id:
            raise Invalid(f"Catalog URL does not identify {item_id}")
        if (platform, item_id) in seen:
            raise Invalid(f"Duplicate (platform, id): {platform}/{item_id}")
        seen.add((platform, item_id))
        if row["status"] not in STATUSES | {"active"}:
            raise Invalid(f"Unknown status for {item_id}: {row['status']!r}")
        rows.append((number, raw, row))
    return lines, headers, header_idx, separator_idx, rows


def media_identities(root: Path) -> dict[str, Path]:
    base = safe_path(root, "media/instagram")
    result: dict[str, Path] = {}
    if not base.exists():
        return result
    if not base.is_dir():
        raise Invalid("media/instagram must be a directory")
    for directory, subdirs, files in os.walk(base, followlinks=False):
        folder = Path(directory)
        for name in subdirs:
            safe_path(root, str(folder / name))
        if "info.json" not in files:
            continue
        info_path = safe_path(root, str(folder / "info.json"))
        info = read_object(info_path)
        item_id = info.get("id", info.get("shortcode"))
        if (not isinstance(item_id, str) or not ID_PATTERN.fullmatch(item_id)
                or info.get("platform") != "instagram"
                or instagram_id(info.get("source_url", info.get("url"))) != item_id
                or ("id" in info and "shortcode" in info and info["id"] != info["shortcode"])
                or ("source_url" in info and "url" in info and instagram_id(info["url"]) != item_id)):
            raise Invalid(f"Unverified info.json identity/source URL: {info_path}")
        if item_id in result:
            raise Invalid(f"Ambiguous media identity {item_id}: {result[item_id]} and {folder}")
        result[item_id] = folder
    return result


def _prepare(root: Path, provider: Optional[str]) -> tuple[dict, dict[Path, tuple[bytes, bytes]]]:
    if not root.expanduser().is_absolute():
        raise Invalid("--root must be an absolute library path")
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise Invalid("The existing library root must be a directory")
    config_path = safe_path(root, ".indexx.json")
    config = read_object(config_path)
    if "root" in config:
        configured = config["root"]
        if not isinstance(configured, str) or not configured.strip() or Path(configured).expanduser().resolve() != root:
            raise Invalid("Config points at another root; migration does not relocate libraries")
    paths = config.get("paths")
    if not isinstance(paths, dict) or paths.get("use_catalog") not in ("legacy", "catalog"):
        raise Invalid("Config requires paths.use_catalog: legacy or catalog")
    key = "instagram_catalog_legacy" if paths["use_catalog"] == "legacy" else "instagram_catalog"
    raw_catalog = paths.get(key)
    if not isinstance(raw_catalog, str) or Path(raw_catalog).is_absolute():
        raise Invalid("Configured catalog must be a relative path inside the library")
    catalog = safe_path(root, raw_catalog)
    relative = catalog.relative_to(root).as_posix()
    # The supported Mac commonly uses a case-insensitive filesystem. Reserve
    # case aliases even when tests or a user's volume happen to be case-sensitive.
    folded = relative.casefold()
    files = {value.casefold() for value in RESERVED_FILES}
    directories = {value.casefold() for value in LIBRARY_DIRECTORIES}
    trees = {value.casefold() for value in RESERVED_TREES}
    if (folded in files or folded in directories or not relative
            or not Path(folded).parts or Path(folded).parts[0] in trees | files):
        raise Invalid(f"Catalog collides with a support, state, or artifact path: {relative}")
    if not catalog.is_file():
        raise Invalid(f"Selected catalog must be an existing file: {relative}")
    # Validate backup destinations even in plan mode; never discover collisions after writes.
    for reserved in ("logs", "logs/migrations"):
        directory = safe_path(root, reserved)
        if directory.exists() and not directory.is_dir():
            raise Invalid(f"Expected a directory: {directory}")
    manifest = safe_path(root, "logs/install.json")
    if manifest.exists() and not manifest.is_file():
        raise Invalid("logs/install.json must be a file")
    updated_config, config_changed = provider_config(config, provider)
    catalog_before = catalog.read_bytes()
    lines, headers, header_idx, separator_idx, rows = legacy_table(catalog_before.decode("utf-8"))
    identities = media_identities(root)
    new_headers = list(headers)
    if "media_path" not in new_headers:
        new_headers.append("media_path")
    if any(row["status"] == "active" for _, _, row in rows) and "legacy_status" not in new_headers:
        new_headers.append("legacy_status")
    added = new_headers[len(headers):]
    def replace(number: int, raw: list[str]) -> None:
        prefix, _, suffix = split_table_line(lines[number])
        lines[number] = prefix + "|" + "|".join(raw) + "|" + suffix
    if added:
        _, raw_headers, _ = split_table_line(lines[header_idx])
        _, raw_separator, _ = split_table_line(lines[separator_idx])
        replace(header_idx, raw_headers + [f" {name} " for name in added])
        replace(separator_idx, raw_separator + [" --- " for _ in added])
    counts: Counter = Counter()
    mapped = 0
    for number, raw, row in rows:
        item_id, status = row["shortcode"], row["status"]
        matched = identities.get(item_id)
        old_path = row.get("media_path", "")
        if old_path:
            specified = safe_path(root, old_path)
            specified_folder = specified.parent if specified.is_file() else specified
            if matched is None or specified_folder != matched:
                raise Invalid(f"Existing media_path for {item_id} has no matching verified info.json")
        elif status == "wiki_ingested" and matched is None:
            raise Invalid(f"Completed claim {item_id} has no verified media folder; resolve its identity before migration")
        values = dict(row)
        if matched is not None and not old_path:
            values["media_path"] = matched.relative_to(root).as_posix()
            mapped += 1
        if status == "active":
            if row.get("legacy_status", "") not in ("", "active"):
                raise Invalid(f"Conflicting legacy_status for {item_id}; original status would be lost")
            values["legacy_status"] = "active"
            values["status"] = "partial" if matched is not None else "discovered"
            counts[values["status"]] += 1
        new_raw = list(raw) + [" " for _ in added]
        for index, name in enumerate(new_headers):
            if values.get(name, "") != row.get(name, ""):
                new_raw[index] = " " + values[name].replace("|", r"\|") + " "
        replace(number, new_raw)
    catalog_after = "".join(lines).encode("utf-8")
    converted = parse_catalog(catalog_after.decode("utf-8"))
    if [row["shortcode"] for row in converted] != [row["shortcode"] for _, _, row in rows]:
        raise Invalid("Migration changed catalog identity/order")
    writes: dict[Path, tuple[bytes, bytes]] = {}
    if catalog_after != catalog_before:
        writes[catalog] = (catalog_before, catalog_after)
    if config_changed:
        writes[config_path] = (config_path.read_bytes(), (json.dumps(updated_config, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    report = {
        "mode": "plan", "root": str(root), "catalog": relative,
        "rows": len(rows), "columns_added": added, "media_paths_added": mapped,
        "active_statuses_converted": dict(counts), "provider": updated_config["stt"].get("provider"),
        "provider_config_changed": config_changed,
        "changed_files": [path.relative_to(root).as_posix() for path in writes],
        "completed_claims_preserved": sum(row["status"] == "wiki_ingested" for _, _, row in rows),
        "artifact_audit": "not_run", "backup": None, "backup_files": {},
        "next_step": "Run the release indexx_status.py audit after support files are updated; format migration does not validate completion.",
    }
    return report, writes


def plan_migration(root: Path, provider: Optional[str] = None) -> dict:
    return _prepare(root, provider)[0]


def atomic_write(path: Path, data: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply_migration(root: Path, provider: Optional[str] = None) -> dict:
    report, writes = _prepare(root, provider)
    report["mode"] = "applied" if writes else "no_changes"
    if not writes:
        return report
    root = Path(report["root"])
    config_path, catalog = root / ".indexx.json", root / report["catalog"]
    originals = {path: path.read_bytes() for path in (config_path, catalog)}
    for path, (before, _) in writes.items():
        if originals[path] != before:
            raise Invalid("Library changed during migration planning; stop other writers and retry")
    parent = safe_path(root, "logs/migrations")
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=parent))
    for path, data in originals.items():
        target = backup / "originals" / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report["backup"] = str(backup)
    report["backup_files"] = {path.relative_to(root).as_posix(): str(backup / "originals" / path.relative_to(root)) for path in originals}
    # Backups of both inputs exist before any original is replaced. Each replacement
    # is atomic; a crash between them is recoverable using this directory and rerun.
    for path, (before, after) in writes.items():
        if safe_path(root, str(path)).read_bytes() != before:
            raise Invalid(f"Library changed while applying migration; backups are at {backup}")
        atomic_write(path, after)
    (backup / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Existing absolute library root")
    parser.add_argument("--apply", action="store_true", help="Apply the plan after timestamped backups")
    parser.add_argument("--provider", choices=("grok", "elevenlabs"), help="Explicit choice for missing/invalid provider; never switches a valid selection")
    args = parser.parse_args()
    try:
        action = apply_migration if args.apply else plan_migration
        print(json.dumps(action(Path(args.root), args.provider), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"Migration stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
