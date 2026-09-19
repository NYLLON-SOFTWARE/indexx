---
name: INDEXX download
description: >-
  Use when downloading Instagram media into the INDEXX media/ tree on the user's Mac after metadata enrichment, via ScrapeCreators durable media URLs. Always estimate credits first.
---
Download public Instagram media into the Mac INDEXX `media/` tree using **ScrapeCreators MCP**.

## Credit estimate (required)
Before calling ScrapeCreators, tell the user approx credits and that credits cost real money; get OK first.
- `v1_instagram_post` + `download_media=true`: ~10 credits per item if media found, else ~1
- Worst-case batch: N × 10. Check `v1_account_credit_balance` before large batches.

## When
Rows at `metadata` without `media_path`. Batch from `batch.download_n` (default 10).

## Steps
1. Resolve root + catalog from `.indexx.json`.
2. Estimate credits → confirm with user.
3. Call `v1_instagram_post` with catalog URL and `download_media=true` (durable URLs).
4. On the **user's Mac**, create `media/instagram/{handle}/{YYYY-MM-DD}_{shortcode}/`. Download into `media.mp4` / image sequence; write `poster.jpg` if available; write write-once `info.json` (fetch_tool: scrapecreators).
5. Validate with ffprobe. Update catalog `media_path` + status `downloaded`, or `unavailable`/`missing`.
6. Never store media bytes on `/workspace`. Skip if valid media already exists.

## Approval
Ask before batch >25 or file estimated >500MB (in addition to the credit OK).
