#!/usr/bin/env python3
"""Rewrite logs/pipeline-progress.md for INDEXX batch stage gates.

Example:
  python3 scripts/indexx_progress.py --root ~/Documents/INDEXX --title "Batch 1" \\
    --row "id=SHORTCODE handle=example watch=running note=…"
  python3 scripts/indexx_progress.py --root ~/Documents/INDEXX --clear
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
STAGES = ["dl", "aud", "watch", "stt", "tags", "wiki"]
GLYPH = {"pending": "○", "running": "…", "done": "✓", "fail": "✗", "skip": "✗"}


def parse_row(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in s.split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--title", default="INDEXX batch")
    ap.add_argument("--row", action="append", default=[])
    ap.add_argument("--clear", action="store_true")
    args = ap.parse_args()
    root = Path(os.path.expanduser(args.root))
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    board = logs / "pipeline-progress.md"
    rows = [] if (args.clear or True) else []
    for r in args.row:
        rows.append(parse_row(r))
    now = datetime.now(tz=PT).strftime("%Y-%m-%d %H:%M %Z")
    header = (
        f"# {args.title}\n\n_Updated {now}_\n\n"
        "| id | handle | " + " | ".join(STAGES) + " | note |\n"
        "|----|--------|" + "|".join(["---"] * len(STAGES)) + "|------|\n"
    )
    body = []
    for row in rows:
        cells = [GLYPH.get(row.get(st, "pending"), row.get(st, "pending")) for st in STAGES]
        body.append(
            f"| {row.get('id', '')} | {row.get('handle', '')} | "
            + " | ".join(cells)
            + f" | {row.get('note', '')} |"
        )
    board.write_text(header + "\n".join(body) + ("\n" if body else ""), encoding="utf-8")
    print(board)


if __name__ == "__main__":
    main()
