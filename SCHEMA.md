# INDEXX schema (library template)

## Catalog

Markdown table (plus YAML cursor front matter for Instagram Saved).

**Cursor fields:** `newest_shortcode`, `watermark_shortcodes`, `oldest_shortcode`, `count`, `updated`, `last_run_mode`, `last_run_at`, `last_clean_stop`.

**Columns:** `shortcode`, `url`, `href_kind`, `type`, `collected_at`, `status`, `media_path`, `updated_at` (extend as needed with handle, caption snippet, duration).

**Statuses:** `discovered` | `metadata` | `downloaded` | `transcribed` | `wiki_ingested` | `unavailable` | `missing` | `failed` | `partial` | `skipped_no_video`

## Item folder

```
media/instagram/{handle}/{YYYY-MM-DD}_{id}/
  media.mp4              # or image sequence
  audio.mp3              # 128 kbps stereo (video items)
  transcript.md          # + Sources links; front matter source/model
  transcript.vtt         # when word timestamps exist
  transcript.words.json  # raw words[] from STT
  info.json              # write-once fetch metadata
  poster.jpg             # optional
```

### transcript.md front matter (example)

```yaml
media: media.mp4
audio: audio.mp3
source: grok_stt
model: grok-voice-transcribe-2.0
```

## Done checklist (`wiki_ingested`)

An item is fully processed only when:

1. Catalog status is `wiki_ingested`
2. Media file present (or honest `skipped_no_video` / `unavailable`)
3. `info.json` present
4. For video: `audio.mp3` (or legacy `audio.wav`)
5. `transcript.md` with Sources links (or honest no-speech note)
6. Word timestamps (`.vtt` / `.words.json`) when speech was transcribed
7. Tags: 5–10 kebab-case
8. Facets:
   - `form:` exactly one (`how-to` | `demo` | `sketch` | `quote` | `talk` | `review` | …)
   - `topic:` 1–3 subject domains
   - `intent:` exactly one (`entertainment` | `inspiration` | `reference` | `learn`)
9. Wiki source page under `wiki/sources/instagram/{id}.md`
10. Creator page on first sight of handle
11. Concepts only at ≥3 sources (or explicit user ask) — never one concept per reel

## Taxonomies

- **Tags** — descriptive keywords (`wiki/taxonomies/tags.md`)
- **Facets** — orthogonal axes, not tag soup (`wiki/taxonomies/facets.md`)
- **Concepts** — backlink graph pages at ≥3 sources

## Lint

Prefer:

```bash
bash scripts/indexx-status.sh
rg -n 'wiki_ingested|transcribed|downloaded' markdown catalog
```

Stay out of binary media when grepping.
