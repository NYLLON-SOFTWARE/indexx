#!/usr/bin/env python3
"""INDEXX library health dashboard — gather stats and write logs/dashboard.html (+ JSON).

Run from library root (or pass --root):
  python3 scripts/indexx_dashboard.py
  python3 scripts/indexx_dashboard.py --root ~/Documents/INDEXX

Never invents metrics: missing values become null / "—" with a gap note.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from indexx_status import Invalid, audit, load_catalog, parse_catalog, strict_json

def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_local(dt: Optional[datetime] = None) -> str:
    d = dt or now_local()
    return d.isoformat(timespec="seconds")


def load_indexx_json(root: Path) -> tuple[Optional[dict], Optional[str]]:
    path = root / ".indexx.json"
    if not path.is_file():
        return None, f".indexx.json not found at {path}"
    try:
        cfg = strict_json(path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            return None, ".indexx.json must be an object"
        return cfg, None
    except Exception as e:
        return None, f"Failed to parse .indexx.json: {e}"


def resolve_catalog_path(root: Path, cfg: Optional[dict]) -> tuple[Optional[Path], Optional[str]]:
    # The selected configured catalog is authoritative; never guess a different file.
    try:
        _, path, _ = load_catalog(root)
        return path, None
    except (Invalid, OSError, UnicodeError, TypeError, ValueError, RuntimeError) as exc:
        return None, str(exc)


def parse_yaml_front_matter(text: str) -> dict[str, Any]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, Any] = {}
    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        # Try JSON-ish values
        if val.startswith("[") or val.startswith("{") or val in ("true", "false", "null"):
            try:
                out[key] = json.loads(val)
                continue
            except Exception:
                pass
        # Strip quotes
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        out[key] = val
    return out


def parse_catalog_table(text: str) -> tuple[list[dict[str, str]], Optional[str]]:
    try:
        return parse_catalog(text), None
    except Invalid as exc:
        return [], str(exc)


def run_status_scripts(root: Path) -> dict[str, Any]:
    """Use the bundled validator directly; never execute scripts found in user data."""
    result = audit(root)
    gaps = list(result["errors"])
    if result["invalid_complete"]:
        gaps.append(f"{result['invalid_complete']} catalog completion claims fail structural validation")
    return {
        "ran": True,
        "commands": [],
        "stdout": json.dumps(result, indent=2),
        "parsed": result,
        "gap": "; ".join(gaps) or None,
    }


def count_wiki_sources(root: Path) -> tuple[Optional[int], Optional[str]]:
    wiki = root / "wiki"
    if not wiki.is_dir():
        return None, "wiki/ directory not present"
    sources = wiki / "sources"
    if sources.is_dir():
        n = sum(1 for p in sources.rglob("*.md") if p.is_file())
        return n, None
    # fallback: any md under wiki except taxonomies/index/log
    skip = {"index.md", "log.md", "tags.md", "facets.md"}
    n = sum(
        1
        for p in wiki.rglob("*.md")
        if p.is_file() and p.name.lower() not in skip and "taxonom" not in str(p).lower()
    )
    return n, "Counted wiki/**/*.md (no wiki/sources/ tree); may include non-source pages"


def count_media_on_disk(root: Path) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Return (item_folders, media_mp4_count, gap)."""
    media = root / "media" / "instagram"
    if media.is_dir():
        gap = None
    else:
        media = root / "media"
        if not media.is_dir():
            return None, None, "media/instagram/ (and media/) not present"
        gap = "Counted under media/ (media/instagram/ missing)"

    try:
        item_dirs = set()
        for p in media.rglob("*"):
            if not p.is_dir():
                continue
            if (
                (p / "media.mp4").is_file()
                or (p / "info.json").is_file()
                or (p / "transcript.md").is_file()
                or (p / "audio.mp3").is_file()
                or (p / "audio.wav").is_file()
            ):
                item_dirs.add(p)
        folders = len(item_dirs)
        mp4s = sum(1 for d in item_dirs if (d / "media.mp4").is_file())
    except Exception as e:
        return None, None, f"Media scan error: {e}"
    return folders, mp4s, gap


def parse_pipeline_progress(root: Path) -> dict[str, Any]:
    path = root / "logs" / "pipeline-progress.md"
    out: dict[str, Any] = {"present": False, "title": None, "rows": [], "gap": None}
    if not path.is_file():
        out["gap"] = "logs/pipeline-progress.md not present"
        return out
    out["present"] = True
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        out["gap"] = f"Could not read pipeline-progress.md: {e}"
        return out

    # Title
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        out["title"] = m.group(1).strip()

    # Parse markdown table rows
    lines = text.splitlines()
    headers: list[str] = []
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if not headers:
            if any(c.lower() in ("id", "shortcode", "handle", "item") for c in cols):
                headers = [c.lower() for c in cols]
                continue
        if headers and re.match(r"^\|\s*[-:]+", line.strip()):
            continue
        if headers:
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            while len(cols) < len(headers):
                cols.append("")
            row = {headers[j]: cols[j] for j in range(len(headers))}
            out["rows"].append(row)
    if not out["rows"]:
        # Keep a short raw excerpt for the dashboard
        out["excerpt"] = "\n".join(lines[:40])
    return out


def gather(root: Path) -> dict[str, Any]:
    gaps: list[str] = []
    cfg, cfg_gap = load_indexx_json(root)
    if cfg_gap:
        gaps.append(cfg_gap)

    catalog_path, cat_gap = resolve_catalog_path(root, cfg)
    if cat_gap:
        gaps.append(cat_gap)

    front: dict[str, Any] = {}
    rows: list[dict[str, str]] = []
    by_status: dict[str, int] = {}
    catalog_downloaded = None
    if catalog_path:
        try:
            text = catalog_path.read_text(encoding="utf-8", errors="replace")
            front = parse_yaml_front_matter(text)
            rows, table_gap = parse_catalog_table(text)
            if table_gap:
                gaps.append(table_gap)
            by_status = dict(Counter((r.get("status") or "(empty)").strip() or "(empty)" for r in rows))
            # catalog says downloaded if status downloaded+ or media_path set
            catalog_downloaded = sum(
                1
                for r in rows
                if (r.get("status") or "") in ("downloaded", "transcribed", "wiki_ingested", "partial")
                or bool((r.get("media_path") or "").strip())
            )
        except Exception as e:
            gaps.append(f"Catalog read error: {e}")

    status = run_status_scripts(root)
    if status.get("gap"):
        gaps.append(status["gap"])

    wiki_n, wiki_gap = count_wiki_sources(root)
    if wiki_gap:
        gaps.append(wiki_gap)

    media_folders, media_mp4s, media_gap = count_media_on_disk(root)
    if media_gap:
        gaps.append(media_gap)

    pipeline = parse_pipeline_progress(root)
    if pipeline.get("gap"):
        gaps.append(pipeline["gap"])

    # Fully processed
    fully = None
    fully_note = None
    sp = status.get("parsed") or {}
    if not sp.get("errors") and isinstance(sp.get("fully_processed"), int):
        fully = sp["fully_processed"]
        fully_note = f"Structurally validated; {sp.get('invalid_complete', 0)} invalid completion claims"
    else:
        fully_note = "Validation unavailable; see data gaps"

    # Failures
    failures = 0
    fail_keys = []
    for k, v in by_status.items():
        lk = k.lower()
        if any(x in lk for x in ("fail", "error", "stuck")):
            failures += v
            fail_keys.append(f"{k}={v}")
    if not fail_keys and isinstance(sp.get("failures"), int):
        failures = sp["failures"]
        fail_keys.append("status_script.failures")

    # Timestamps
    last_checked = (
        front.get("last_run_at")
        or front.get("updated")
        or (cfg or {}).get("last_crawl_at")
        or (cfg or {}).get("updated")
        or sp.get("last_checked")
        or sp.get("last_run_at")
    )
    watermarks = front.get("watermark_shortcodes") or (cfg or {}).get("watermark_shortcodes")

    total_saved = None
    if rows:
        total_saved = len(rows)
    elif front.get("count") is not None:
        try:
            total_saved = int(front["count"])
        except Exception:
            total_saved = None
        gaps.append("Used front-matter count (table rows unavailable or empty)")
    elif isinstance(sp.get("total"), int):
        total_saved = sp["total"]

    data = {
        "generated_at": iso_local(),
        "generated_at_label": now_local().strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "library_root": str(root),
        "indexx": {
            "present": cfg is not None,
            "canonical": (cfg or {}).get("canonical"),
            "root": (cfg or {}).get("root"),
            "paths": (cfg or {}).get("paths"),
            "batch": (cfg or {}).get("batch"),
            "raw_keys": sorted(cfg.keys()) if isinstance(cfg, dict) else [],
        },
        "catalog": {
            "path": str(catalog_path) if catalog_path else None,
            "total_rows": total_saved,
            "by_status": by_status,
            "front_matter": {
                k: front.get(k)
                for k in (
                    "source",
                    "updated",
                    "newest_shortcode",
                    "oldest_shortcode",
                    "count",
                    "last_run_mode",
                    "last_run_at",
                    "last_clean_stop",
                    "watermark_shortcodes",
                )
                if k in front
            },
            "downloaded_estimate": catalog_downloaded,
        },
        "fully_processed": {"count": fully, "note": fully_note},
        "failures": {"count": failures, "breakdown": fail_keys},
        "timestamps": {
            "last_checked": last_checked,
            "watermarks": watermarks,
            "catalog_updated": front.get("updated"),
            "last_run_at": front.get("last_run_at"),
            "last_run_mode": front.get("last_run_mode"),
        },
        "media": {
            "item_folders": media_folders,
            "media_mp4_count": media_mp4s,
            "catalog_downloaded_estimate": catalog_downloaded,
        },
        "wiki": {"sources_count": wiki_n},
        "status_script": status,
        "pipeline": pipeline,
        "gaps": gaps,
    }
    return data


def fmt_num(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:,}"
    return str(v)


def render_html(data: dict[str, Any]) -> str:
    by_status = data["catalog"]["by_status"] or {}
    status_rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td class='num'>{fmt_num(v)}</td></tr>"
        for k, v in sorted(by_status.items(), key=lambda kv: (-kv[1], kv[0]))
    ) or "<tr><td colspan='2' class='muted'>No status breakdown available</td></tr>"

    gaps = data.get("gaps") or []
    gaps_html = (
        "<ul class='gaps'>" + "".join(f"<li>{html.escape(g)}</li>" for g in gaps) + "</ul>"
        if gaps
        else "<p class='ok'>No data gaps reported.</p>"
    )

    pipe = data.get("pipeline") or {}
    pipe_rows = pipe.get("rows") or []
    if pipe_rows:
        # compact: use keys from first row
        keys = list(pipe_rows[0].keys())
        thead = "".join(f"<th>{html.escape(k)}</th>" for k in keys)
        body = ""
        for r in pipe_rows[:40]:
            body += "<tr>" + "".join(f"<td>{html.escape(str(r.get(k, '')))}</td>" for k in keys) + "</tr>"
        pipe_html = f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"
        if len(pipe_rows) > 40:
            pipe_html += f"<p class='muted'>Showing 40 of {len(pipe_rows)} rows.</p>"
    elif pipe.get("excerpt"):
        pipe_html = f"<pre class='excerpt'>{html.escape(pipe['excerpt'])}</pre>"
    else:
        pipe_html = f"<p class='muted'>{html.escape(pipe.get('gap') or 'No active batch board.')}</p>"

    ts = data.get("timestamps") or {}
    media = data.get("media") or {}
    fully = data.get("fully_processed") or {}
    fails = data.get("failures") or {}

    wm = ts.get("watermarks")
    if isinstance(wm, list):
        wm_s = ", ".join(str(x) for x in wm[:12]) + ("…" if len(wm) > 12 else "")
    else:
        wm_s = str(wm) if wm is not None else "—"

    status_out = (data.get("status_script") or {}).get("stdout") or ""
    status_block = (
        f"<pre class='excerpt'>{html.escape(status_out[:6000])}</pre>"
        if status_out
        else f"<p class='muted'>{html.escape((data.get('status_script') or {}).get('gap') or 'Status script not run.')}</p>"
    )

    cards = [
        ("Total saved", data["catalog"]["total_rows"], "Catalog rows"),
        ("Fully processed", fully.get("count"), fully.get("note") or "wiki_ingested"),
        ("Failures", fails.get("count"), ", ".join(fails.get("breakdown") or []) or "fail/error/stuck"),
        ("Last checked", ts.get("last_checked"), ts.get("last_run_mode") or "crawl / watermark"),
        ("Media on disk", media.get("media_mp4_count"), f"item folders: {fmt_num(media.get('item_folders'))}"),
        ("Wiki sources", data["wiki"]["sources_count"], "wiki/sources/**/*.md"),
    ]

    cards_html = "".join(
        f"""
        <div class="card">
          <div class="label">{html.escape(title)}</div>
          <div class="value">{html.escape(fmt_num(value))}</div>
          <div class="sub">{html.escape(sub or '')}</div>
        </div>"""
        for title, value, sub in cards
    )

    cat_path = data["catalog"].get("path") or "—"
    root = data.get("library_root") or "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>INDEXX Status</title>
<style>
  :root {{
    --bg: #0d1117;
    --panel: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --good: #3fb950;
    --bad: #f85149;
    --warn: #d29922;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text);
  }}
  h1 {{ font-size: 22px; margin: 0 0 4px; font-weight: 600; }}
  h2 {{ font-size: 15px; margin: 28px 0 10px; color: var(--accent); font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }}
  .meta {{ color: var(--muted); font-size: 12px; margin-bottom: 20px; }}
  .meta code {{ background: var(--panel); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border); }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
  }}
  .card .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
  .card .value {{ font-size: 28px; font-weight: 650; margin: 6px 0 4px; font-variant-numeric: tabular-nums; }}
  .card .sub {{ color: var(--muted); font-size: 11px; min-height: 1.2em; }}
  .panel {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    overflow-x: auto;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 550; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }}
  td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  .muted {{ color: var(--muted); }}
  .ok {{ color: var(--good); }}
  .gaps {{ margin: 0; padding-left: 18px; color: var(--warn); }}
  .gaps li {{ margin: 4px 0; }}
  pre.excerpt {{
    margin: 0; white-space: pre-wrap; word-break: break-word;
    font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    color: var(--muted); max-height: 320px; overflow: auto;
  }}
  .kv {{ display: grid; grid-template-columns: 160px 1fr; gap: 6px 12px; font-size: 13px; }}
  .kv .k {{ color: var(--muted); }}
  footer {{ margin-top: 28px; color: var(--muted); font-size: 11px; }}
</style>
</head>
<body>
  <h1>INDEXX library status</h1>
  <div class="meta">
    Generated <strong>{html.escape(data.get('generated_at_label') or data.get('generated_at') or '—')}</strong>
    · root <code>{html.escape(root)}</code>
    · catalog <code>{html.escape(cat_path)}</code>
  </div>

  <div class="grid">
    {cards_html}
  </div>

  <h2>Status breakdown</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Status</th><th style="text-align:right">Count</th></tr></thead>
      <tbody>{status_rows}</tbody>
    </table>
  </div>

  <h2>Timestamps &amp; watermarks</h2>
  <div class="panel kv">
    <div class="k">Last checked</div><div>{html.escape(str(ts.get('last_checked') or '—'))}</div>
    <div class="k">Catalog updated</div><div>{html.escape(str(ts.get('catalog_updated') or '—'))}</div>
    <div class="k">Last run at</div><div>{html.escape(str(ts.get('last_run_at') or '—'))}</div>
    <div class="k">Last run mode</div><div>{html.escape(str(ts.get('last_run_mode') or '—'))}</div>
    <div class="k">Watermarks</div><div>{html.escape(wm_s)}</div>
    <div class="k">Media vs catalog</div><div>disk mp4={html.escape(fmt_num(media.get('media_mp4_count')))} · catalog downloaded≈{html.escape(fmt_num(media.get('catalog_downloaded_estimate')))}</div>
  </div>

  <h2>Active batch</h2>
  <div class="panel">
    <div class="muted" style="margin-bottom:8px">{html.escape(pipe.get('title') or 'pipeline-progress')}</div>
    {pipe_html}
  </div>

  <h2>Status script</h2>
  <div class="panel">{status_block}</div>

  <h2>Data gaps</h2>
  <div class="panel">{gaps_html}</div>

  <footer>
    Refresh: <code>python3 scripts/indexx_dashboard.py</code> from the library root.
    Companion JSON: <code>logs/dashboard-data.json</code>. Offline file:// OK · inline CSS only.
  </footer>
</body>
</html>
"""


def write_outputs(root: Path, data: dict[str, Any]) -> tuple[Path, Path]:
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    html_path = logs / "dashboard.html"
    json_path = logs / "dashboard-data.json"
    html_path.write_text(render_html(data), encoding="utf-8")
    json_path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return html_path, json_path


def find_root(cli_root: Optional[str]) -> Path:
    if cli_root:
        return Path(os.path.expanduser(cli_root)).resolve()
    # Prefer cwd if it looks like an INDEXX root
    cwd = Path.cwd().resolve()
    if (cwd / ".indexx.json").is_file() or (cwd / "markdown").is_dir():
        return cwd
    # script lives in <root>/scripts/
    here = Path(__file__).resolve().parent.parent
    if (here / ".indexx.json").is_file() or (here / "markdown").is_dir():
        return here
    return cwd


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build INDEXX local status dashboard")
    ap.add_argument("--root", help="Library root (default: cwd or parent of scripts/)")
    ap.add_argument("--print-json", action="store_true", help="Also print JSON to stdout")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not root.is_dir():
        print(f"Library root not found: {root}", file=sys.stderr)
        return 1

    data = gather(root)
    html_path, json_path = write_outputs(root, data)
    print(f"Wrote {html_path}")
    print(f"Wrote {json_path}")
    print(f"Generated at {data.get('generated_at_label')}")
    print(f"Total saved: {data['catalog']['total_rows']}")
    print(f"Fully processed: {data['fully_processed']['count']}")
    print(f"Failures: {data['failures']['count']}")
    if args.print_json:
        print(json.dumps(data, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
