# Contributing

## Bot template vs this repo

- **Grok Bot / app store template** — profile, skills, memories, routines. Best for end users who want chat behavior without cloning.
- **This repository** — MIT-licensed on-disk scaffolding (`AGENTS.md`, `SCHEMA.md`, examples, scripts, skill markdown sources). Best for contributors and for mirroring the library layout on a Mac.

When changing skills:

1. Edit `skills/<name>/SKILL.md` here.
2. Keep `docs/bot-share-payload.json` in sync if you maintain a shareable export (or regenerate it from the live bot).
3. Prefer **Grok Voice Transcribe 2.0** as primary STT; ElevenLabs optional; ScrapeCreators = IG metadata/download only.
4. Never commit media, transcripts of personal content, real catalogs, `.env`, or API keys.
5. No personal paths (`/Users/…`), usernames, or private shortcodes in docs or skills.

## PRs

- Keep skills path-portable (resolve from `.indexx.json`).
- Scrub PII before opening a PR: no personal usernames, no `/Users/<name>` paths, no key-shaped tokens. Documenting the env var *name* `XAI_API_KEY` is fine.
