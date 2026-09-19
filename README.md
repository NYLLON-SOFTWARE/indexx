# INDEXX

**INDEXX** is a personal media wiki for Instagram Saved (and later other sources). Honest markdown catalog, media **on your computer**, **Grok Voice Transcribe 2.0**, tags + facets, compiled wiki pages.

This repo is the **open-source library + skill sources** (MIT). Day-to-day you run INDEXX as a **Grok Bot**; the bot scaffolds your Mac library and runs the pipeline.

## Install (recommended)

1. **Install [Grok Bot](https://grok.x.ai/)** (or open Grok Bot if you already have it).
2. **Add the INDEXX bot** from the Grok Bot marketplace / shared template (or clone this repo and import the bot profile + skills).
3. In chat with INDEXX, say: **`install INDEXX`** or **`set up INDEXX`**.
4. The bot **asks where to store your library**, then creates that folder and wires connectors. Suggested defaults:
   - **Mac:** `~/Documents/INDEXX` (may sync via iCloud Documents)
   - **Windows:** `%USERPROFILE%\Documents\INDEXX` (may sync via OneDrive Documents)
   - **Linux:** `~/INDEXX`
   You can pick any path. You only approve the path, vault secrets, and any paid credit estimates.

Grok Bot’s desktop app runs on **macOS, Windows, and Linux**; register that computer so the bot can write the library on disk.

You should **not** need to hand-copy folders. Manual layout docs live in `AGENTS.md` / `SCHEMA.md` for power users.

## Bot install checklist

Have INDEXX confirm each item (it can drive most of this once you approve):

### In Grok Bot
- [ ] INDEXX bot installed / imported
- [ ] **`XAI_API_KEY`** in the vault (primary STT — Grok Voice Transcribe 2.0)
- [ ] **ScrapeCreators** custom MCP connected (Instagram metadata + downloads only — **not** transcripts); API key in vault
- [ ] **ElevenLabs** connected *(optional)* — Scribe fallback STT
- [ ] Registered Mac / computer linked so the bot can write your library on disk
- [ ] First-run: ask **`set up INDEXX`** → bot asks for library location → root created, `.indexx.json` written, catalog + wiki stubs ready

### On your Mac (bot will ask / check)
- [ ] Homebrew tools: `brew install ripgrep ffmpeg`
- [ ] **Choose library location** — bot asks; suggested defaults: Mac `~/Documents/INDEXX`, Windows `%USERPROFILE%\Documents\INDEXX`, Linux `~/INDEXX` — you confirm or pick another path
- [ ] Library root exists at the path you chose — **never copy `media/` into the Grok Bot `/workspace`**. Note: Mac `Documents` may sync via **iCloud**, Windows `Documents` via **OneDrive**; if you want media only on-disk, pick a path outside cloud-synced folders (e.g. `~/INDEXX`, `%USERPROFILE%\INDEXX`, or an external volume).

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

**Never store media on the Grok Bot `/workspace`.** ScrapeCreators = metadata + durable download URLs only — never transcripts.

**Cloud-folder note:** Mac may sync `Desktop` / `Documents` via **iCloud**; Windows often syncs `Documents` via **OneDrive**. That is separate from the Grok Bot `/workspace`. Suggested Documents defaults are convenient but can upload `media/` to Apple/Microsoft if those sync features are on. Prefer a non-synced path when local-only media matters.

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
