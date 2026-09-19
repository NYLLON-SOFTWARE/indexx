---
name: INDEXX transcribe
description: >-
  Use when transcribing downloaded INDEXX media with the provider selected during setup: Grok Voice Transcribe 2.0 (recommended) or optional ElevenLabs Scribe. Co-locate media, audio, and transcripts; estimate cost before paid calls. Never switch providers automatically.
---
Transcribe INDEXX Instagram (and later source) items into `transcript.md` beside the media.

## Use the selected provider

Read `stt.provider` from `.indexx.json`: `grok` or `elevenlabs`. If missing, null, invalid, or only legacy `stt.primary` / `stt.fallback` exists, run the setup provider-choice step before any paid transcription. Grok is recommended; ElevenLabs is an optional user-selected alternative, not an automatic fallback. Follow a valid saved selection even when the other provider is installed or authenticated.

Only the selected provider's credentials are required. If it is unavailable, pause and explain the issue; ask before switching, update the saved selection only on an explicit choice, and re-estimate the cost. Never send the same audio to the other provider automatically.

1. **When `stt.provider` is `grok`: Grok Voice Transcribe 2.0 (recommended)** via xAI STT (`POST https://api.x.ai/v1/stt`).
   - Model: `grok-voice-transcribe-2.0` (always set explicitly).
   - Auth: `XAI_API_KEY` in the secure vault / box secrets only — **never** chat, skills, catalog, wiki, or `.indexx.json`.
   - Word timestamps: response `words[]` with `start` / `end` (seconds) → write `transcript.vtt` + `transcript.words.json`.
   - Recommended flags: `language=en`, `format=true`; optional `diarize=true`; optional repeated `keyterm=` (≤100, from handle/caption/cast).
   - List price (as of 2026-09): **~$0.10/hr** REST batch (diarize + keyterms included). Streaming ~$0.20/hr — prefer batch for INDEXX files.
   - Prefer estimate first (duration × rate), then get an explicit OK before spend on large batches.
   - If `XAI_API_KEY` is missing, stop and ask the user to add it via secure secret card.
2. **When `stt.provider` is `elevenlabs`: ElevenLabs Scribe** via the ElevenLabs connector. Connect/authenticate it only when selected; no `XAI_API_KEY` is required for this route. Use the available Scribe transcription tool with word timestamps and record the actual model used. Estimate from the current selected plan/model rate and get OK before spend.

**Grok video watch** remains optional visual/no-speech triage, separate from the transcription provider selection. It is not a substitute for STT when speech needs a transcript.

**Never use ScrapeCreators for transcripts.** ScrapeCreators is metadata + media download only.
**Never use mlx-whisper** (or other local Whisper).

## Co-locate media + audio + transcripts

Keep everything in the **same item folder**. Never park audio or transcripts elsewhere.

```
media/instagram/{handle}/{YYYY-MM-DD}_{id}/
  media.mp4
  audio.mp3
  transcript.md
  transcript.vtt
  transcript.words.json
  info.json
```

## Audio extract (recommended always)

```bash
ffmpeg -i media.mp4 -vn -codec:a libmp3lame -b:a 128k -ac 2 audio.mp3
```

Do **not** re-download Instagram just to get audio. ffprobe-check duration vs `media.mp4` (flag if delta > ~0.5s).

## transcript.md must point at sources

Front matter must record the provider and actual model used: `source: grok_stt` with `model: grok-voice-transcribe-2.0` for Grok, or `source: elevenlabs_scribe` with the actual Scribe model for ElevenLabs. Link `media.mp4` / `audio.mp3` under Sources. Never label ElevenLabs output as Grok output.

## Word timestamps

- `transcript.md` — readable text + Sources
- `transcript.vtt` — WebVTT from word array
- `transcript.words.json` — selected provider's word timestamps normalized to `text`/`start`/`end` (seconds) and optional `speaker`; preserve the source/model in transcript front matter

## Cost estimate (required)

Before a paid transcription batch: name the selected provider, tell approx cost, and get explicit OK for large batches. Grok REST ≈ duration_hours × $0.10; for ElevenLabs, use the current selected plan/model rate. Approval for one provider does not authorize switching to another.

## Steps

1. Resolve paths and `stt.provider` from `.indexx.json`; complete provider selection if needed.
2. Confirm local media; download first if missing.
3. Ensure `audio.mp3` beside `media.mp4`.
4. Optional Grok-watch for no-speech triage.
5. Check the selected provider's credentials; estimate cost → confirm when required.
6. If `grok`, call `POST /v1/stt` with `model=grok-voice-transcribe-2.0` (+ language/format/optional diarize/keyterms). If `elevenlabs`, use its Scribe transcription tool. Do not call both.
7. Write transcript files; set catalog `transcribed`.
8. Empty/music-only → honest no-speech note.
9. Never silently rewrite a good transcript — backup prior files on explicit re-run.

## Approval

- Paid STT batches (always estimate; OK for large batches).
- Batch >25 items.
