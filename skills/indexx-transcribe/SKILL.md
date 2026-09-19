---
name: INDEXX transcribe
description: >-
  Use when transcribing INDEXX media after download — Grok Voice Transcribe 2.0 primary STT (xAI API, XAI_API_KEY in vault); co-locate media.mp4 + audio.mp3 + transcripts; Grok watch for visuals/no-speech. Never ScrapeCreators transcript. Never mlx-whisper. ElevenLabs optional fallback only. Always estimate cost before paid calls.
---
Transcribe INDEXX Instagram (and later source) items into `transcript.md` beside the media.

## Provider priority (local media)

1. **Grok Voice Transcribe 2.0** via xAI STT (`POST https://api.x.ai/v1/stt`) — **primary STT**
   - Model: `grok-voice-transcribe-2.0` (always set explicitly; default without `model` is still 1.0).
   - Auth: `XAI_API_KEY` in the secure vault / box secrets only — **never** chat, skills, catalog, wiki, or `.indexx.json`.
   - Word timestamps: response `words[]` with `start` / `end` (seconds) → write `transcript.vtt` + `transcript.words.json`.
   - Recommended flags: `language=en`, `format=true`; optional `diarize=true`; optional repeated `keyterm=` (≤100, from handle/caption/cast).
   - List price (as of 2026-09): **~$0.10/hr** REST batch (diarize + keyterms included). Streaming ~$0.20/hr — prefer batch for INDEXX files.
   - Prefer estimate first (duration × rate), then get an explicit OK before spend on large batches.
   - If `XAI_API_KEY` is missing, stop and ask the user to add it via secure secret card.
2. **ElevenLabs Scribe** — **optional fallback** only (e.g. cold-open / music-event sensitive clips) via ElevenLabs connector. Estimate + OK before spend (~$0.22/hr batch).
3. **Grok video watch** — free; visuals + “is there speech?” / music-only notes. Not a substitute for STT when speech needs a transcript.

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

Front matter should record provider + model (`source: grok_stt`, `model: grok-voice-transcribe-2.0`) and link `media.mp4` / `audio.mp3` under Sources.

## Word timestamps

- `transcript.md` — readable text + Sources
- `transcript.vtt` — WebVTT from word array
- `transcript.words.json` — raw Grok `words` (`text`/`start`/`end`[/`speaker`])

## Cost estimate (required)

Before any paid xAI or ElevenLabs transcription batch: tell approx cost, get explicit OK for large batches. Grok REST ≈ duration_hours × $0.10.

## Steps

1. Resolve paths from `.indexx.json`.
2. Confirm local media; download first if missing.
3. Ensure `audio.mp3` beside `media.mp4`.
4. Optional Grok-watch for no-speech triage.
5. Estimate cost → confirm when required.
6. `POST /v1/stt` with `model=grok-voice-transcribe-2.0` (+ language/format/optional diarize/keyterms).
7. Write transcript files; set catalog `transcribed`.
8. Empty/music-only → honest no-speech note.
9. Never silently rewrite a good transcript — backup prior files on explicit re-run.

## Approval

- Paid STT batches (always estimate; OK for large batches).
- Batch >25 items.
