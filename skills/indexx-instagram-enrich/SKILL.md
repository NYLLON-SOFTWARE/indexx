---
name: INDEXX instagram enrich
description: >-
  Use when INDEXX catalog rows need type + metadata enrichment after discovery (caption, creator, real reel-vs-post) via ScrapeCreators before download. Always estimate credits first.
---
Enrich INDEXX catalog rows with public Instagram metadata via **ScrapeCreators MCP** (`user-scrapecreators`).

## Credit estimate (required)
Before calling ScrapeCreators, tell the user approx credits and that credits cost real money; get OK first.
- Metadata only (`v1_instagram_post`, no download_media): ~1 credit × N items
- Prefer `cache_max_age` when re-fetching. Check `v1_account_credit_balance` before large batches.

## When
Rows at `discovered` / untyped, or user asks to enrich N items. Batch from `.indexx.json` `batch.enrich_n` (default 20).

## Steps
1. Resolve catalog path from `.indexx.json` (`paths.use_catalog`).
2. Estimate credits → confirm with user.
3. Pick next rows needing enrich (status `discovered` or empty type).
4. For each shortcode, call MCP `v1_instagram_post` with the catalog URL (or `https://www.instagram.com/p/{shortcode}/` / `/reel/{shortcode}/`). Prefer `trim=true`. Do **not** set `download_media` here.
5. Map response → catalog: resolved `type` (reel|post|carousel|image), creator handle, caption snippet, taken_at, duration. Fix href_kind vs real type.
6. Status → `metadata` (or `unavailable` on public 404 / private / age-gate). Never delete the row.
7. Report counts + credits used if known.

## Limits
Public data only. Saved discovery is not this skill.
