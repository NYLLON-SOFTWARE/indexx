---
name: INDEXX progress
description: >-
  Use during any multi-item INDEXX batch to maintain logs/pipeline-progress.md and stage-gate chat pings for real-time visual status.
---
Keep a live visual progress board during INDEXX multi-item batches.

## Board file
`logs/pipeline-progress.md` in the library root (Mac canonical).

Rewrite via:
```bash
python3 scripts/indexx_progress.py --root "$ROOT" --title "Batch name" \
  --row "id=SHORTCODE handle=foo watch=running note=…"
```
Use `--clear` when starting a new batch.

## Glyphs / stages
- Glyphs: `○` pending · `…` running · `✓` done · `✗` fail/skip
- Stages: `dl` download · `aud` audio.mp3 · `watch` Grok watch · `stt` selected-provider transcription · `tags` tags/facets · `wiki` wiki ingest

## Chat convention
At every stage gate, rewrite the board **and** send one short chat ping (what flipped). Do not dump the whole table every time. At batch end, quote or attach the final board.

Also keep the in-chat todo checklist updated. Point the user at the agent computer preview if they want to watch desktop work live.

## Policy reminders
- STT uses `.indexx.json` → `stt.provider`, selected during setup: Grok Voice Transcribe 2.0 (recommended) or optional ElevenLabs Scribe. Never switch automatically; never ScrapeCreators transcript or mlx-whisper.
- Estimate + OK before ScrapeCreators download spend or paid STT spend
