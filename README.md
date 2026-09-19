# INDEXX

**INDEXX** is a personal media wiki for Instagram Saved (and later other sources). Honest markdown catalog, media **on your computer**, **Grok Voice Transcribe 2.0**, tags + facets, compiled wiki pages.

This repo is the **open-source library + skill sources** (MIT). Day-to-day you run INDEXX as a **Grok Bot**; the bot scaffolds your Mac library and runs the pipeline.

## Install (recommended)

1. **Install [Grok Bot](https://grok.x.ai/)** (or open Grok Bot if you already have it).
2. **Add the INDEXX bot** from the Grok Bot marketplace / shared template (or clone this repo and import the bot profile + skills).
3. In chat with INDEXX, say: **`install INDEXX`** or **`set up INDEXX`**.
4. The bot walks the checklist below, creates `~/Documents/INDEXX` (or a path you choose), and wires connectors. You only approve vault secrets and any paid credit estimates.

You should **not** need to hand-copy folders. Manual layout docs live in `AGENTS.md` / `SCHEMA.md` for power users.

## Bot install checklist

Have INDEXX confirm each item (it can drive most of this once you approve):

### In Grok Bot
- [ ] INDEXX bot installed / imported
- [ ] **`XAI_API_KEY`** in the vault (primary STT — Grok Voice Transcribe 2.0)
- [ ] **ScrapeCreators** custom MCP connected (Instagram metadata + downloads only — **not** transcripts); API key in vault
- [ ] **ElevenLabs** connected *(optional)* — Scribe fallback STT
- [ ] Registered Mac / computer linked so the bot can write your library on disk
- [ ] First-run: ask **`set up INDEXX`** → library root created, `.indexx.json` written, catalog + wiki stubs ready

### On your Mac (bot will ask / check)
- [ ] Homebrew tools: `brew install ripgrep ffmpeg`
- [ ] Library root exists (default `~/Documents/INDEXX`) — **media stays here, never in the cloud workspace**

### After setup
- [ ] Credit OK before first ScrapeCreators enrich/download batch
- [ ] STT cost OK before first paid transcription batch (~$0.10/hr Grok)
- [ ] Smoke test: enrich → download → transcribe → wiki one Saved item

## What stays local (privacy)

| Stays on your machine | OK in cloud bot workspace |
|----------------------|---------------------------|
| `media/` (mp4, mp3, posters) | Skills / bot profile |
| Transcripts beside media | Catalog / wiki markdown sync (optional) |
| API keys / Instagram session | Never — vault / connect cards only |

**Never store media on `/workspace`.** ScrapeCreators = metadata + durable download URLs only — never transcripts.

## Primary transcription

1. **Grok Voice Transcribe 2.0** — primary STT (`XAI_API_KEY` in vault only)
2. **ElevenLabs Scribe** — optional fallback
3. **Grok video watch** — free visuals / no-speech triage

Do **not** use ScrapeCreators transcript endpoints or mlx-whisper.

## Pipeline

`discovered` → `metadata` → `downloaded` → `transcribed` → `wiki_ingested`

Done = catalog `wiki_ingested` **and** SCHEMA checklist green (`SCHEMA.md`).

## Skills (this repo)

| Skill | Purpose |
|-------|---------|
| `indexx-setup` | First-run library + connectors |
| `indexx-add` | Front door (Saved / URL / profile) |
| `indexx-instagram-saves-index` | Crawl Instagram Saved → catalog |
| `indexx-instagram-enrich` | Metadata via ScrapeCreators |
| `indexx-download` | Download media to Mac |
| `indexx-transcribe` | Grok Voice Transcribe 2.0 |
| `indexx-wiki-ingest` | Tags, facets, wiki pages |
| `indexx-query` / `indexx-lint` / `indexx-progress` | Query, health, live batch board |
| `indexx-sync` | Markdown-only Mac ↔ workspace (stub) |

## License

MIT — Copyright 2026 INDEXX contributors. See [LICENSE](LICENSE).
