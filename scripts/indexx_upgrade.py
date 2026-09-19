#!/usr/bin/env python3
"""Read-only, cumulative checks for work an existing library needs after updates.

Recompute from source files, not install revision or a dismissed notification.
No cache rebuild, completion flags, file writes, network, or media-byte reads.
This checks feature prerequisites; it does not replace the artifact audit or
an evidence-based review of wiki content.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

# A check-only invocation must not create imported helpers' __pycache__ files.
sys.dont_write_bytecode = True
import indexx_search as search


def report(root: Path) -> dict:
    root = search._root(root)
    inputs, items, _, _, _ = search._snapshot(root)
    completed = [item for item in items if item["status"] == "wiki_ingested"]
    pending = [item["id"] for item in completed
               if item["source_path"] and not item["people_reviewed"]]
    blocked = [item["id"] for item in completed if not item["source_path"]]
    reviewed = sum(item["people_reviewed"] for item in completed)
    excluded = sum(item["status"] in ("unavailable", "skipped_no_video") for item in items)

    try:
        index = search.index_status(root)
    except (OSError, ValueError, sqlite3.DatabaseError, KeyError, TypeError) as exc:
        index = {"fresh": False, "error": str(exc)}

    # Do not report readiness from a mixture of different library states.
    if search._current_manifest(root, inputs.manifest) != inputs.manifest:
        raise ValueError("Library inputs changed during checking; retry when the writer finishes")

    # Keep stable, cumulative check IDs as new releases add prerequisites. A user
    # may skip releases or defer work, so installed SHA never suppresses a check.
    checks = [
        {
            "id": "local-search-v1",
            "title": "Fast local search",
            "status": "ready" if index["fresh"] else "attention",
            "why": "Search needs an index built from the current library and search format.",
            "action": "Rebuild the derived index during an update; check-only requests leave it unchanged.",
            "automatic_on_update": True,
            "index": index,
        },
        {
            "id": "existing-story-people-v1",
            "title": "Find existing stories by the person speaking or featured",
            "status": "attention" if pending or blocked else "ready",
            "why": "Older wiki stories can be valid but lack reviewed person attributions. Rebuilding search does not add them.",
            "action": "Say 'Refresh existing stories' to review retained evidence and update cited wiki pages. Missing evidence stays unknown.",
            "automatic_on_update": False,
            "eligible_count": len(completed),
            "reviewed_count": reviewed,
            "pending_count": len(pending),
            "pending_ids": pending,
            "blocked_count": len(blocked),
            "blocked_ids": blocked,
            "blocked_reason": "Missing, unreadable, or identity-invalid source pages need inspection before review." if blocked else None,
        },
        {
            "id": "search-inputs-v1",
            "title": "Search input warnings",
            "status": "attention" if inputs.warnings else "ready",
            "why": "A fresh index can still omit malformed pages or annotations.",
            "action": "Inspect the listed files and errors. Review format repairs against backups while preserving cited content; do not infer missing facts.",
            "automatic_on_update": False,
            "warning_count": len(inputs.warnings),
            "warnings": inputs.warnings,
        },
    ]
    return {
        "report_version": 1,
        "status": "attention" if any(check["status"] != "ready" for check in checks) else "ready",
        "scope": {
            "catalog_total": len(items),
            "claimed_complete_stories": len(completed),
            "unprocessed_backlog": len(items) - len(completed) - excluded,
            "terminal_excluded": excluded,
        },
        "checks": checks,
        "suggested_reply": "Refresh existing stories" if pending or blocked else None,
        "scope_note": "Existing-story refresh covers catalog items already marked wiki_ingested, not the unprocessed backlog. These checks do not certify semantic quality or identify people without retained evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Existing absolute library path")
    args = parser.parse_args()
    try:
        result = report(args.root)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"report_version": 1, "status": "blocked", "errors": [str(exc)]}, indent=2))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0  # Pending work is a successful check, not a failed installation.


if __name__ == "__main__":
    raise SystemExit(main())
