---
name: INDEXX setup
description: >-
  Use when a user first runs INDEXX, has no library folder yet, or asks to change the library location or transcription provider.
---
First-run and re-setup for the INDEXX library on the **user's computer**. Keep this skill generic: no hardcoded usernames or machine IDs.

## Portable agent rules
- The shareable Grok Bot is: profile description + skills + profile memories + routines.
- The library on disk (`AGENTS.md`, `.indexx.json`, catalog/media/wiki) is per-user data. Skills resolve paths from `.indexx.json` or by asking.
- Never put Instagram cookies, API keys, or passwords in markdown, skills, or `.indexx.json`.

## Transcription provider (ask during setup)

Ask **"Which transcription service would you like INDEXX to use?"** with two choices:

1. **Grok Voice Transcribe 2.0 (recommended)** — xAI transcription via `grok-voice-transcribe-2.0`; requires `XAI_API_KEY` in the vault. Store `stt.provider: "grok"`.
2. **ElevenLabs Scribe** — optional alternative for users who prefer it; connect the ElevenLabs plugin only if selected. Authenticate through its secure connection flow. Store `stt.provider: "elevenlabs"`.

Explain that audio is sent to the selected provider and transcription is paid; estimate that provider's cost before a batch. Grok is the recommendation, but require the user's choice rather than silently selecting it. On first setup, if unanswered, leave `stt.provider` null and pause transcription; other setup can continue. When changing providers, retain the previous selection until the user confirms a replacement; cancellation leaves it unchanged.

Preserve an existing valid selection unless the user asks to change it. For an older config with only `stt.primary` / `stt.fallback`, ask once for the provider, write `stt.provider`, and remove those legacy fields. An installed plugin or available key is not a provider selection. Never install or require both providers, and never switch providers automatically after a missing key, failure, or rate limit. Offer a switch only for the user to choose explicitly.

## Required connectors

- **Selected transcription provider only:** check its credentials/connection; missing xAI credentials must not block a user who selected ElevenLabs, and vice versa. Never put credentials in chat, markdown, or `.indexx.json`.
- **ScrapeCreators:** required for public Instagram **metadata + durable media URLs / downloads only**, not transcripts. Custom remote MCP; API key in the vault. Estimate credits and get OK before spend.

Never use ScrapeCreators or mlx-whisper for transcripts.

## Local tools (recommend for every install)
On the user's Mac (Homebrew):

1. **ripgrep** (`rg`) — **recommended for everyone**; default fast search for catalog/wiki/lint. `brew install ripgrep`. Check with `command -v rg`; if missing, ask them to install before treating lint search as fully set up.
2. **ffmpeg** — extract **`audio.mp3`** (128 kbps stereo) beside `media.mp4` for STT:
   `ffmpeg -i media.mp4 -vn -codec:a libmp3lame -b:a 128k -ac 2 audio.mp3`
   Then ffprobe-check duration vs video. `brew install ffmpeg`.

Do **not** install or recommend mlx-whisper.

Also document connectors + these tools in library `AGENTS.md` and `README.md` when scaffolding.

## Steps
1. Check agent memory / existing `.indexx.json` for a data root. If present and the folder exists, reuse it unless they asked to move it; continue to the provider and connector checks.
2. For a new or relocated library, **ask where to store it** (widget). Do not silently create a folder.
   - Detect OS when possible and **suggest** a default, but require an explicit confirm or a custom path:
     - **Mac:** `~/Documents/INDEXX` (note: may sync via **iCloud** Documents)
     - **Windows:** `%USERPROFILE%\Documents\INDEXX` (note: may sync via **OneDrive** Documents)
     - **Linux / other:** `~/INDEXX`
   - If they want media only on-disk (not vendor cloud), suggest a non-synced path (Mac/Linux `~/INDEXX`, Windows `%USERPROFILE%\INDEXX`, or an external volume).
   - Grok Bot desktop runs on macOS, Windows, and Linux — the registered computer is where the library is created.
3. On their computer (registered machine Shell), expand `~` and create the tree from AGENTS.md (catalog, markdown/instagram legacy catalog, media, wiki, logs, db/scripts) plus `AGENTS.md`, `SCHEMA.md`, `README.md`, `.indexx.json`, `.gitignore`. If data exists, reuse — never wipe.
4. For a new library, write `.indexx.json` with absolute `root`, `canonical: mac`, `cloud_workspace: /workspace/INDEXX`, `paths.use_catalog: legacy`, legacy + target catalog paths, `cloud_workspace_forbidden: ["media"]`, and `stt.provider: null`. Preserve existing configuration when re-running setup.
5. Ensure Instagram catalog exists (empty cursor + table) via the saves-index skill conventions.
6. Ask for the transcription provider as described above if not selected or the user asks to change it, persist the answer in `stt.provider`, then check only that provider's credentials plus ScrapeCreators MCP. Connect ElevenLabs only when chosen. Keys via connect card / vault — never paste into chat.
7. Check `rg` and `ffmpeg` on their Mac; if missing, recommend `brew install ripgrep` and/or `brew install ffmpeg` as part of first-run.
8. Store absolute root in agent profile memory. Tell the user the path and selected transcription provider (or that selection is pending); remind them media must not go to Grok Bot `/workspace`, and iCloud sync is their choice via path.

## Rules
- User computer by default. **Ask before choosing the library path**; suggest the OS default above, never assume. Never move/delete a root without an explicit ask. No media on `/workspace`.
