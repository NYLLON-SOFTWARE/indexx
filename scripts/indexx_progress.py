#!/usr/bin/env python3
"""Update an INDEXX progress row without losing earlier rows or stage results.

The JSON sidecar is authoritative; Markdown is a rebuildable view. Existing
Markdown-only boards are migrated on first use. Example:
  python3 scripts/indexx_progress.py --root "$ROOT" --title "Batch 1" \\
    --row 'id=SHORTCODE handle=example watch=running note="Checking speech"'
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shlex
import tempfile
from datetime import datetime
from pathlib import Path

STAGES = ["dl", "aud", "watch", "stt", "tags", "wiki"]
GLYPH = {"pending": "○", "running": "…", "done": "✓", "fail": "✗", "skip": "−"}
FIELDS = {"id", "handle", "note", *STAGES}
DEFAULT_TITLE = "INDEXX batch"


def check_containment(root: Path, *paths: Path) -> None:
    """Reject existing or dangling symlinks that redirect progress outside root."""
    for path in paths:
        try:
            path.resolve().relative_to(root)
        except ValueError:
            raise ValueError(f"Progress path resolves outside the library: {path.name}") from None


def validate_row(row: object) -> dict[str, str]:
    if not isinstance(row, dict) or not all(isinstance(v, str) for v in row.values()):
        raise ValueError("Each progress row must contain text fields")
    if set(row) - FIELDS:
        raise ValueError("Unknown progress fields: " + ", ".join(sorted(set(row) - FIELDS)))
    if not row.get("id", "").strip():
        raise ValueError("Every --row needs a nonempty id")
    for stage in STAGES:
        if stage in row and row[stage] not in GLYPH:
            raise ValueError(f"Invalid {stage} state {row[stage]!r}; use {', '.join(GLYPH)}")
    return row


def parse_row(value: str) -> dict[str, str]:
    row: dict[str, str] = {}
    for part in shlex.split(value):
        if "=" not in part:
            raise ValueError("Row fields must be key=value; quote notes containing spaces")
        key, val = part.split("=", 1)
        if key in row:
            raise ValueError(f"Duplicate row field: {key}")
        row[key] = val
    return validate_row(row)


def merge_rows(rows: list[dict[str, str]], updates: list[dict[str, str]]) -> list[dict[str, str]]:
    by_id = {row["id"]: dict(row) for row in rows}
    for update in updates:
        by_id.setdefault(update["id"], {}).update(update)
    return list(by_id.values())


def read_legacy(board: Path) -> dict:
    lines = board.read_text(encoding="utf-8").splitlines()
    title = next((line[2:] for line in lines if line.startswith("# ")), DEFAULT_TITLE)
    columns = ["id", "handle", *STAGES, "note"]
    table_found = False
    rows = []
    legacy_states = {"○": "pending", "…": "running", "✓": "done", "✗": "fail", "−": "skip"}
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if cells == columns:
            table_found = True
            continue
        if not table_found or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) < len(columns):
            raise ValueError("Cannot migrate malformed Markdown progress row")
        # The old writer did not escape pipes in notes; the last column owns any extras.
        cells = cells[:8] + [" | ".join(cells[8:])]
        row = dict(zip(columns, (cell.replace(r"\|", "|") for cell in cells)))
        for stage in STAGES:
            row[stage] = legacy_states.get(row[stage], row[stage])
        rows.append(validate_row(row))
    if not table_found:
        raise ValueError("Existing progress Markdown has no recognizable table; preserve it or use --clear")
    return {"version": 1, "title": title, "rows": merge_rows([], rows)}


def load_state(sidecar: Path, board: Path) -> dict:
    if not sidecar.exists():
        return read_legacy(board) if board.exists() else {"version": 1, "title": DEFAULT_TITLE, "rows": []}
    state = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("Unsupported progress state format; original files were preserved")
    if not isinstance(state.get("title"), str) or not isinstance(state.get("rows"), list):
        raise ValueError("Invalid progress state; original files were preserved")
    for row in state["rows"]:
        validate_row(row)
    if len({row["id"] for row in state["rows"]}) != len(state["rows"]):
        raise ValueError("Duplicate IDs in progress state; original files were preserved")
    return state


def markdown_text(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"([\\`*_{\[\]()#|}])", r"\\\1", escaped)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def render(state: dict, now: datetime) -> str:
    header = (
        f"# {markdown_text(state['title'])}\n\n_Updated {now.strftime('%Y-%m-%d %H:%M %Z%z')}_\n\n"
        "| id | handle | " + " | ".join(STAGES) + " | note |\n"
        "|----|--------|" + "|".join(["---"] * len(STAGES)) + "|------|\n"
    )
    body = []
    for row in state["rows"]:
        cells = [row["id"], row.get("handle", "")]
        cells += [GLYPH[row.get(stage, "pending")] for stage in STAGES]
        cells += [row.get("note", "")]
        body.append("| " + " | ".join(markdown_text(cell) for cell in cells) + " |")
    return header + "\n".join(body) + ("\n" if body else "")


def atomic_write(path: Path, content: str) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--title", help="New title; omitted preserves the current title")
    ap.add_argument("--row", action="append", default=[], help="Quoted key=value fields; merged by id")
    ap.add_argument("--clear", action="store_true", help="Start a new board before applying rows")
    args = ap.parse_args()
    try:
        updates = [parse_row(value) for value in args.row]
        root = Path(args.root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("Library root must already exist")
        logs = root / "logs"
        board, sidecar = logs / "pipeline-progress.md", logs / "pipeline-progress.json"
        # Validate every target before reading state, even when --clear skips loading it.
        check_containment(root, logs, sidecar, board)
        state = {"version": 1, "title": DEFAULT_TITLE, "rows": []} if args.clear else load_state(sidecar, board)
        if args.title is not None:
            if not args.title.strip():
                raise ValueError("Title cannot be empty")
            state["title"] = args.title
        state["rows"] = merge_rows(state["rows"], updates)
        now = datetime.now().astimezone()
        state["updated_at"] = now.isoformat(timespec="seconds")
        logs.mkdir(parents=True, exist_ok=True)
        check_containment(root, logs, sidecar, board)
        # Commit state first: an interrupted Markdown write is repaired on the next invocation.
        atomic_write(sidecar, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        check_containment(root, logs, board)
        atomic_write(board, render(state, now))
    except (ValueError, OSError, RuntimeError) as exc:
        ap.exit(2, f"Progress update failed: {exc}\n")
    print(board)


if __name__ == "__main__":
    main()
