---
name: INDEXX instagram saves index
description: >-
  Use when collecting or refreshing Instagram Saved posts/reels into the INDEXX markdown catalog (first crawl or incremental update), including watermark fail-safes and progress pings.
---
Collect shortcodes from the signed-in user's Instagram **Saved** into the INDEXX markdown catalog. Markdown is the ledger and crawl cursor.

## Resolve paths
Read `<root>/.indexx.json`. If `paths.use_catalog` is `legacy` (default), open `paths.instagram_catalog_legacy`. Else `paths.instagram_catalog`. No hardcoded usernames.

## Catalog shape
YAML cursor + newest-first table. Required cursor fields: `newest_shortcode`, `watermark_shortcodes`, `oldest_shortcode`, `count`, `updated`, `last_run_mode`, `last_run_at`, `last_clean_stop`. Columns: shortcode, url, href_kind, type, collected_at, status, media_path, updated_at.

## Watermark rules
- Multi-ID watermark (top 5–10). Incremental stop when **any** reappears; prepend new rows only.
- First run: scroll until no growth; set watermarks from top.
- Fallback if no watermark seen: bounded merge; never delete rows; do not advance watermarks; set `last_run_mode: fallback`; alert the user.
- Advance watermarks only after a clean stop.

## Fail-safes
Un-save ≠ delete. Login/CAPTCHA/2FA → stop and hand desktop (no password storage). Milestone pings ~every 25 new IDs. DOM href extraction only (`/p/`, `/reel/`, `/tv/`). Store `href_kind`; resolve real type later at enrich.

## Out of scope
Does not download, transcribe, or wiki-ingest. Catalog stays on the user's computer.
