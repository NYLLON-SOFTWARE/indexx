---
name: INDEXX add
description: >-
  Use when the user wants to add something to INDEXX — refresh Instagram Saved, paste a single IG/X URL, or pull last N posts from @handle.
---
Front door for adding media to INDEXX. Parse the user's intent and route — do not make them pick a skill by name.

## Routes
| Utterance | Job | Next skill |
|-----------|-----|------------|
| refresh / crawl my Saved | `saved` | [INDEXX Instagram saves index](sand-workflow:indexx-instagram-saves-index) |
| paste instagram.com/p\|reel\|tv\|stories\|highlights URL | `url` | stub: enrich→download→transcribe→wiki (when those skills are live) |
| last N from @handle (default N=100; ask if N>100) | `profile` | discover into per-handle catalog only; no unattended wiki-ingest of all N |
| x.com/.../status/... | `x-url` | stub until X skills land |

## Rules
- Dedup on `(platform, id)`. One media folder per id even if Saved + URL + profile all saw it.
- Single URL may run end-to-end when download/transcribe skills exist. Profile harvests are discover-only batches.
- Stories ~24h TTL: download immediately or report missed.
- Read root from `.indexx.json`. No secrets in chat.
- If the target skill is still a stub, say what is scaffolded vs not and stop after catalog intent is recorded.
