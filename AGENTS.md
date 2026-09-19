# INDEXX — agent notes (library template)

Copy this file to the **library root** on the user's computer (e.g. `~/Documents/INDEXX/AGENTS.md`). Skills resolve paths from `.indexx.json` — never hardcode usernames or machine IDs.

## What INDEXX is

Personal media wiki: Instagram Saved → markdown catalog → local media → transcript → tags/facets → wiki pages. The shareable Grok Bot is profile + skills + memories + routines. This on-disk tree is per-user data.

## Canonical paths

- **Canonical library:** user's computer (`canonical: mac` in `.indexx.json`).
- **Cloud workspace:** `/workspace/INDEXX` may hold markdown copies only.
- **Forbidden on cloud:** anything under `media/` (and raw media bytes anywhere on the box).
- **iCloud:** `~/Documents` / Desktop may sync to Apple iCloud independently of the bot. Use a non-iCloud path if media must stay off Apple’s cloud.

## Connectors

1. **xAI / Grok Voice Transcribe 2.0** — primary STT. `XAI_API_KEY` in vault only.
2. **ScrapeCreators** — custom remote MCP for public IG **metadata + durable media URLs / downloads**. Not transcripts. API key in vault.
3. **ElevenLabs** — optional Scribe fallback.

Estimate cost/credits and get OK before paid batches.

## Local tools

- `rg` (ripgrep) — preferred search for lint/query
- `ffmpeg` — `audio.mp3` at 128 kbps stereo beside `media.mp4`

## Tree

```
<library-root>/
  .indexx.json
  AGENTS.md
  SCHEMA.md
  README.md
  .gitignore
  catalog/                    # target catalog location
  markdown/instagram/         # legacy saves-index.md catalog
  media/instagram/{handle}/{YYYY-MM-DD}_{id}/
    media.mp4
    audio.mp3
    transcript.md
    transcript.vtt
    transcript.words.json
    info.json
  wiki/
    index.md
    log.md
    sources/instagram/
    entities/creators/
    concepts/
    taxonomies/tags.md
    taxonomies/facets.md
    syntheses/
  logs/
  scripts/
```

## Status flow

`discovered` → `metadata` → `downloaded` → `transcribed` → `wiki_ingested`

## Rules

- No API keys, cookies, or passwords in markdown, skills, or `.indexx.json`.
- Dedup on `(platform, id)`.
- Never invent wiki synthesis; cite shortcodes / wikilinks.
- Batch sizes from `.indexx.json` (`batch.*`); default process remaining work in batches of ~20.
