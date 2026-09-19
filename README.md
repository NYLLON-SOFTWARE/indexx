# INDEXX

**INDEXX** is a personal media wiki for Instagram Saved (and later other sources). Honest markdown catalog, media **on your computer**, transcription with **Grok Voice Transcribe 2.0 (recommended)** or your choice of **ElevenLabs Scribe**, tags + facets, compiled wiki pages.

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
5. Choose your transcription service: **Grok Voice Transcribe 2.0 (recommended)** or **ElevenLabs Scribe (optional alternative)**. INDEXX saves the choice and connects only the service you select. It does not install ElevenLabs by default or switch providers automatically.

Grok Bot’s desktop app runs on **macOS, Windows, and Linux**; register that computer so the bot can write the library on disk.

You should **not** need to hand-copy folders. Manual layout docs live in `AGENTS.md` / `SCHEMA.md` for power users.

## Bot install checklist

Have INDEXX confirm each item (it can drive most of this once you approve):

### In Grok Bot
- [ ] INDEXX bot installed / imported
- [ ] **Transcription provider selected during setup** and saved in `.indexx.json` (`stt.provider`)
- [ ] **Selected provider connected:** `XAI_API_KEY` in the vault for Grok, or the authenticated ElevenLabs plugin if you chose Scribe; the other provider is not required
- [ ] **ScrapeCreators** custom MCP connected (Instagram metadata + downloads only — **not** transcripts); API key in vault
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

## Choose transcription during setup

Setup asks which service you want:

| Choice | Setup |
| --- | --- |
| **Grok Voice Transcribe 2.0 (recommended)** | Save `stt.provider: "grok"`; add `XAI_API_KEY` through the vault |
| **ElevenLabs Scribe (optional alternative)** | Save `stt.provider: "elevenlabs"`; connect/authenticate ElevenLabs only if chosen |

Audio is sent to the selected provider for paid transcription. INDEXX estimates its cost before processing. A missing key or service error pauses transcription; it does not trigger a call to another provider. You can change your selection by asking INDEXX to change the transcription provider. Existing transcripts are preserved unless you explicitly request retranscription.

The example config leaves `stt.provider` null until you choose. Older configs with `stt.primary` / `stt.fallback` prompt for a choice once during setup. Optional **Grok video watch** is separate visual/no-speech triage, not the transcription service.

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
| `indexx-transcribe` | Selected provider: Grok (recommended) or optional ElevenLabs Scribe |
| `indexx-wiki-ingest` | Tags, facets, wiki pages |
| `indexx-query` / `indexx-lint` / `indexx-progress` | Query, health, live batch board |
| `indexx-sync` | Markdown-only Mac ↔ workspace (stub) |

## License

MIT — Copyright 2026 INDEXX contributors. See [LICENSE](LICENSE).
