---
name: INDEXX lint
description: >-
  Use after crawls, after ~20 wiki ingests, on a weekly health check, or when asking what is done vs still needs processing in the INDEXX library.
---
Report backlog vs done and wiki health. Punch list only unless asked to apply fixes.

## Done definition

An item is fully processed only when:
1. Catalog status is `wiki_ingested`
2. SCHEMA item checklist passes: media file, info.json, audio.mp3 (or legacy audio.wav) for video, transcript.md with Sources, word timestamps if speech, tags (5–10), facets (form one / topic 1–3 / intent one), wiki source page

Anything earlier (`discovered`…`transcribed`, or `partial`) is still open.

## How to check

Prefer **ripgrep (`rg`)** — recommended for every INDEXX install (`brew install ripgrep`). From library root:

```bash
bash scripts/indexx-status.sh
# or
python3 scripts/indexx_status.py

rg -n 'wiki_ingested|transcribed|downloaded' markdown catalog
rg -L --glob '**/transcript.md' '^facets:' media/
rg -g '!media/**/*.mp4' -g '!media/**/*.mp3' -g '!media/**/*.wav' 'comedy' markdown wiki media
```

If `rg` is missing, say so and recommend install; temporary fallback is stock `grep` + the Python status script (stay out of binary media).

Also flag: orphan wiki pages, singleton/near-duplicate tags, concept pages with <3 sources, rows stuck >14 days, broken wikilinks, watermark sanity.

Append findings to `wiki/log.md` when asked. Do not auto-rewrite the wiki.
