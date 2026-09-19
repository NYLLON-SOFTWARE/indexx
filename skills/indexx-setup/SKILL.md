---
name: INDEXX setup
description: >-
  Use when a user first runs INDEXX, has no library folder yet, or asks to set up / change where the INDEXX library lives.
---
First-run and re-setup for the INDEXX library on the **user's computer**. Keep this skill generic: no hardcoded usernames or machine IDs.

## Portable agent rules
- The shareable Grok Bot is: profile description + skills + profile memories + routines.
- The library on disk (`AGENTS.md`, `.indexx.json`, catalog/media/wiki) is per-user data. Skills resolve paths from `.indexx.json` or by asking.
- Never put Instagram cookies, API keys, or passwords in markdown, skills, or `.indexx.json`.

## Required connectors (tell every new installer)
Before enrich / download / primary transcription works, the bot needs these connectors. Walk the user through connecting them on first run if missing:

1. **xAI / Grok Voice Transcribe 2.0** — **primary STT** (`grok-voice-transcribe-2.0`). Put `XAI_API_KEY` in the vault only — never chat or markdown. Estimate cost (~$0.10/hr) and get OK before large batches. Never use ScrapeCreators or mlx-whisper for transcripts.
2. **ElevenLabs Scribe** — **optional fallback** only (vault via connect card). Estimate + OK before spend.
3. **ScrapeCreators** — required for public Instagram **metadata + durable media URLs / downloads only** — **not** transcripts. Custom remote MCP; API key in the vault. Estimate credits and get OK before spend.

If `XAI_API_KEY` is missing, say so clearly. Grok watch can still describe visuals / no-speech for free.

## Local tools (recommend for every install)
On the user's Mac (Homebrew):

1. **ripgrep** (`rg`) — **recommended for everyone**; default fast search for catalog/wiki/lint. `brew install ripgrep`. Check with `command -v rg`; if missing, ask them to install before treating lint search as fully set up.
2. **ffmpeg** — extract **`audio.mp3`** (128 kbps stereo) beside `media.mp4` for STT:
   `ffmpeg -i media.mp4 -vn -codec:a libmp3lame -b:a 128k -ac 2 audio.mp3`
   Then ffprobe-check duration vs video. `brew install ffmpeg`.

Do **not** install or recommend mlx-whisper.

Also document connectors + these tools in library `AGENTS.md` and `README.md` when scaffolding.

## Steps
1. Check agent memory / existing `.indexx.json` for a data root. If present and the folder exists, confirm briefly and stop (unless they asked to move it).
2. If unknown, ask with a widget; default `~/Documents/INDEXX`; allow custom path.
3. On their computer (registered machine Shell), expand `~` and create the tree from AGENTS.md (catalog, markdown/instagram legacy catalog, media, wiki, logs, db/scripts) plus `AGENTS.md`, `SCHEMA.md`, `README.md`, `.indexx.json`, `.gitignore`. If data exists, reuse — never wipe.
4. Write `.indexx.json` with absolute `root`, `canonical: mac`, `cloud_workspace: /workspace/INDEXX`, `paths.use_catalog: legacy`, legacy + target catalog paths, `cloud_workspace_forbidden: ["media"]`.
5. Ensure Instagram catalog exists (empty cursor + table) via the saves-index skill conventions.
6. Check connectors/secrets: `XAI_API_KEY` (required for STT) + ScrapeCreators MCP (required for IG metadata/download). ElevenLabs optional. Keys via connect card / vault — never paste into chat.
7. Check `rg` and `ffmpeg` on their Mac; if missing, recommend `brew install ripgrep` and/or `brew install ffmpeg` as part of first-run.
8. Store absolute root in agent profile memory. Tell the user the path; remind them media stays on their Mac.

## Rules
- User computer by default. Never move/delete a root without an explicit ask. No media on `/workspace`.
