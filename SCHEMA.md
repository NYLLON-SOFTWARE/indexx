# INDEXX schema (library template)

## Configuration and catalog

`.indexx.json` contains the absolute local library `root`, `canonical: "mac"`, selected `paths`, `batch` sizes, and explicitly chosen `stt.provider` (`grok` or `elevenlabs`). A new installation has `stt.provider: null` until the user chooses. Provider credentials stay in the vault/connection. No automatic fallback. Existing transcripts retain their historical provider when the saved preference changes.

`paths.use_catalog` is `legacy` or `catalog`. The corresponding `instagram_catalog_legacy` or `instagram_catalog` path is authoritative and must resolve inside the library. The validator takes `--root` as the library location; it never guesses another catalog if configuration is absent or broken.

`legacy` selects a file location, not an older parsing format. Both locations follow the table contract below. A selected catalog must not overlap configuration, support files, install logs, media, or wiki artifacts. Use `scripts/indexx_migrate.py` from the pinned source checkout to preview legacy format changes, then `--apply` for a backed-up migration. It preserves IDs, row order, extra columns, and cursor metadata. Replaced statuses are retained in `legacy_status`; unfinished entries can have an empty `media_path`. Existing completion claims are not validated by format conversion and still need a full artifact audit.

The catalog is one Markdown pipe table, with a header and `| --- |` separator. Every row has exactly the header's number of cells; escape literal pipes as `\|`. Required columns: `shortcode`, `url`, `type`, `status`, `media_path`. Recommended columns: `href_kind`, `collected_at`, `updated_at`, `handle`. Optional `platform` defaults to `instagram`. `(platform, shortcode)` is unique. `media_path` identifies the item folder or an existing file within it, relative to the library (absolute paths inside the library also work).

Instagram Saved may have cursor front matter: `newest_shortcode`, `watermark_shortcodes`, `oldest_shortcode`, `count`, `updated`, `last_run_mode`, `last_run_at`, `last_clean_stop`.

Statuses: `discovered` → `metadata` → `downloaded` → `transcribed` → `wiki_ingested`; also `unavailable`, `missing`, `failed`, `partial`, `skipped_no_video`. `unavailable` and `skipped_no_video` are excluded terminal outcomes, **not successfully ingested items**. `missing`, `failed`, and `partial` remain backlog. An image-only item can be `wiki_ingested` after its image and wiki checks pass; it does not need fabricated audio or transcripts. Unsupported mixed video carousels stay `partial` until every asset has a supported representation.

## Item folder and metadata

```text
media/instagram/{handle}/{YYYY-MM-DD}_{id}/
  media.mp4              # video items
  audio.mp3              # 128 kbps stereo; legacy audio.wav accepted
  transcript.md          # video: readable speech or explicit no-speech note
  transcript.vtt         # speech only
  transcript.words.json  # speech only, normalized records below
  info.json
  image-01.jpg           # image-only items; list every image in info.json
  poster.jpg             # optional; does not substitute for media
```

All required files must be real, nonempty files. Text must contain non-whitespace content. Referenced paths, including symlink targets, must remain inside the library and item folder as appropriate. `info.json` is a JSON object; preserve fetched metadata and update processing fields separately. A completed video example:

```json
{
  "id": "Example123",
  "platform": "instagram",
  "handle": "example_creator",
  "type": "video",
  "source_url": "https://www.instagram.com/reel/Example123/",
  "duration_seconds": 12.4,
  "fetch_tool": "scrapecreators",
  "transcript_status": "speech",
  "stt": {"provider": "grok", "model": "grok-voice-transcribe-2.0"}
}
```

`id` (legacy alias `shortcode`) and `source_url` (legacy alias `url`) must identify the catalog item. `handle` has no `@`. Normalized `type` is `video`, `image`, or `carousel` (image-only). A video corresponds to catalog `video`, `reel`, or `post`; an image corresponds to `image` or `post`. If `duration_seconds` is present, it must be positive and finite; timestamps must fit within it, allowing 0.5 seconds for rounding.

`transcript_status` is `speech` or `no_speech` for video; `not_applicable` for images. Image-only metadata also requires `image_files: ["image-01.jpg", "image-02.jpg"]`, with every local image represented; `type: "image"` has exactly one image. Preserve the upstream response separately in an optional `fetched_metadata` object.

For no-speech video, record a nonempty `no_speech_reason` in both `info.json` and transcript front matter. The transcript must explicitly state “No speech” and describe the basis (for example, music-only audio). Do not infer no speech from a failed/empty API response. If STT was used, retain its source/model; if a visual/audio review established no speech without STT, use `source: visual_triage` and omit the STT `model`. Audio remains required for video; a video with no usable audio track stays `partial` until that case is explicitly supported.

New transcriptions record `info.json.stt.provider` and `stt.model`. Older items may omit `stt`; when present, it must match the transcript's historical provenance. Changing `.indexx.json` provider preferences does not invalidate old transcripts.

## Supported front matter

The standard-library validator intentionally supports a small, unambiguous YAML subset: opening/closing `---` on their own lines; one top-level `key: value` per line; plain unquoted strings or JSON values. Use **inline JSON arrays and objects** for tags/facets, and double-quoted JSON strings for values needing escaping. No nested YAML, block lists, aliases, multiline strings, duplicate keys, or inline comments. Blank lines and full-line comments are allowed. Quote IDs/handles if they could be interpreted as JSON numbers, `true`, `false`, or `null`.

A completed video's `transcript.md`:

```markdown
---
media: media.mp4
audio: audio.mp3
source: grok_stt
model: grok-voice-transcribe-2.0
transcript_status: speech
tags: ["practice", "learning", "habits", "focus", "reflection"]
facets: {"form":"talk","topic":["learning"],"intent":"learn"}
---
The readable, source-grounded transcript goes here.

## Sources
- [Video](media.mp4)
- [Audio](audio.mp3)
```

For ElevenLabs, use `source: elevenlabs_scribe` and the actual model used. For new Grok requests, explicitly select and record `grok-voice-transcribe-2.0`. Historical `grok-voice-transcribe-1.0` transcripts remain valid when that was the model actually used; never relabel old output as 2.0 or retranscribe it merely to satisfy a model preference. Local Markdown links beneath a `Sources` heading must resolve to the item's video and audio. Keep transcript text or a no-speech note before that heading.

Every wiki source at `wiki/sources/instagram/{id}.md` has the same `tags` and `facets` as its video transcript (image-only items have them only on the source page), plus `id`, `platform`, and `handle` matching metadata:

```yaml
---
id: "Example123"
platform: instagram
handle: example_creator
tags: ["practice", "learning", "habits", "focus", "reflection"]
facets: {"form":"talk","topic":["learning"],"intent":"learn"}
---
```

Follow front matter with a substantive source-grounded body and citations. The creator page `wiki/entities/creators/{handle}.md` must contain text. Tags are 5–10 unique kebab-case strings. Facets contain exactly `form` (one kebab-case string), `topic` (1–3 unique kebab-case strings), and `intent` (one of `entertainment`, `inspiration`, `reference`, `learn`). Use the library taxonomies for the actual meanings; structural validation does not judge classification quality.

## People and source attribution

Source pages may include two additional front matter fields:

```yaml
people: [{"id":"alan-watts","name":"Alan Watts","role":"speaker","evidence":"Caption explicitly credits Alan Watts as the speaker"}]
people_reviewed: true
```

`people` is an inline JSON array. Each record contains exactly `id` (the stable kebab-case person slug), `name` (the canonical display name), `role`, and a nonempty `evidence` string describing the retained source evidence for that identity and role. Each `(id, role)` pair is unique within a source. The supported roles are `speaker` (the person speaks), `featured` (the person is a subject or participant), and `mentioned` (the source refers to them). Merely mentioning a name does not support `speaker`. Keep the supporting caption, explicit attribution, self-identification, or other evidence available in the source or its underlying artifacts, and cite it in the source body. An uploader handle is separate from the identities in the media.

Never assert identity from a voice or appearance resemblance, model familiarity, or a diarization label such as `speaker-0`. Preserve uncertainty in prose without adding an unsupported person record. Reuse reviewed person IDs across uploader handles, but do not merge different people because names happen to match.

`people_reviewed` is an optional boolean, defaulting to `false`. `true` requires an explicit `people` list; `true` with `[]` means a completed evidence review identified no people. Missing/false review flags indicate incomplete coverage, not that a person is absent. Valid evidence-supported entries may be indexed while review is incomplete. Both fields are optional for existing libraries: absent fields do not invalidate old completion claims, trigger transcript rewrites, or authorize a backlog annotation pass. People metadata belongs on source pages; it need not be copied into `info.json` or transcripts.

Every referenced person has `wiki/entities/people/{id}.md`, separate from `wiki/entities/creators/{handle}.md`. Person front matter uses the same supported format:

```markdown
---
id: alan-watts
name: Alan Watts
aliases: []
---
The caption identifies Alan Watts as the speaker in [Example123](../../sources/instagram/Example123.md). This source discusses learning through practice.
```

`id` matches the filename stem and source person IDs. `name` matches the canonical display name in source records. `aliases` is a JSON array of known alternate names; it may be empty. Do not invent aliases. The body must be substantive and cite the associated source pages, explaining what this library's sources support rather than adding an uncited biography. New sources update this shared page across creators; preserve prior citations and describe material disagreements. A person page can be supported by one source; the three-source rule applies to concept pages.

## Local search and watch views

The catalog, item artifacts, and Markdown wiki remain authoritative. `db/search.sqlite3` is a private, derived SQLite FTS5 database; rebuild it from existing files with `python3 scripts/indexx_search.py build --root /path/to/library`. The build does not alter transcripts, annotate people, validate all completion claims, or make provider calls. `python3 scripts/indexx_search.py status --root /path/to/library` reports freshness and coverage. Queries fail on missing/stale data so callers must rebuild before using the results as current.

Use `query --root /path/to/library --person "Alan Watts" --role speaker --type video --all` with `scripts/indexx_search.py` to enumerate every matching indexed record. Exact person matching uses the reviewed identity, canonical name, and aliases, independently of uploader handles. Use `--text "anxiety"` for full-text retrieval, optionally with those filters. Text retrieval finds matching words; it does not guarantee every semantically related item. Report source/person-review coverage alongside counts, especially for legacy items with no annotations. An exhaustive result is exhaustive within the indexed, recorded evidence, not proof of completeness across unavailable or unreviewed media.

`python3 scripts/indexx_watch.py --root /path/to/library --person "Alan Watts" --role speaker --type video --name alan-watts` creates `wiki/views/alan-watts.html` and `wiki/views/alan-watts.md`. These local snapshots include all matching records and distinguish playable files from missing media. HTML is for a local browser; Markdown embeds require the **library root as the Obsidian vault root**. Playback availability does not establish artifact completion. Do not promise inline playback in Grok chat. Rebuild the index and regenerate views after relevant changes. Neither output is authorization to download missing files or publish/upload the library.

## Word timestamps

`transcript.words.json` is a **normalized JSON array**, not a raw provider response:

```json
[
  {"text":"Hello", "start":0.12, "end":0.48, "speaker":"speaker-1"},
  {"text":"world.", "start":0.49, "end":0.93, "speaker":"speaker-1"}
]
```

For ElevenLabs, map `speaker_id` to `speaker` when nonempty and keep only entries whose `type` is `word`; `spacing` and `audio_event` entries are not spoken words. Retain provider event descriptions in the readable narrative, clearly marked as events. This mapping follows the [ElevenLabs response types](https://elevenlabs.io/insights/speech-to-text-api-integration).

Illustrative provider entry → normalized entry (unchanged text and timing):

```json
{"text":"Hello", "start":0.12, "end":0.48, "type":"word", "speaker_id":"speaker_0"}
```

```json
{"text":"Hello", "start":0.12, "end":0.48, "speaker":"speaker_0"}
```

Use actual provider records, not these illustrative values. Omit `speaker` if no speaker ID was returned. Preserve original text/timing, including overlaps; do not invent times, spoken words, or speaker identities. If there are no word records, review the audio before deciding `no_speech`; a provider failure or missing timing data is `partial`.

Only `text`, `start`, `end`, and optional `speaker` are allowed. Text and speaker (when present) are nonempty strings. Times are finite seconds; starts are nonnegative and ordered, each end is greater than its start. Overlap is permitted for overlapping speakers. Preserve actual timing; do not invent timestamps when a provider fails to return them (leave `partial`).

`transcript.vtt` is normalized WebVTT: `WEBVTT`, a blank line, then cues separated by blank lines. Each cue has optional identifier, `HH:MM:SS.mmm --> HH:MM:SS.mmm` (or `MM:SS.mmm`) and nonempty text. Starts are ordered and each end follows its start. This format excludes cue settings, styles, and metadata blocks. Both timestamp files are required for `speech`; neither is required for explicitly documented `no_speech`.

## Completion and audits

Before changing a status, check that item's artifacts:

```bash
python3 scripts/indexx_status.py --root /path/to/library --id Example123 --ready
```

Only after exit code 0 should the bot mark that item `wiki_ingested`. This readiness check does **not** require the status to be complete already. It does not write files or change status. Existing `unavailable`/`skipped_no_video` items must be intentionally resolved before re-entering ingestion.

Audit completion claims with:

```bash
python3 scripts/indexx_status.py --root /path/to/library --json
bash scripts/indexx-status.sh /path/to/library
```

The audit validates every `wiki_ingested` item and exits nonzero for corrupt completion claims or invalid configuration/catalog structure. Ordinary unfinished backlog does not fail the audit. Counts distinguish `claimed_complete`, structurally validated `fully_processed`, `invalid_complete`, `backlog`, and `terminal_excluded`. `--id ID` audits one selected item's completion, while still reporting library counts; an invalid selected item fails. With `--id ID --ready`, the selected item's result controls the exit code. Full audits remain necessary after batches.

The dashboard uses the validator's actual complete count; it never treats the number of `wiki_ingested` labels as proof. A validator error means “needs review/repair,” not permission to erase metadata, invent missing artifacts, retranscribe, or incur new charges. Legacy front matter can be normalized without changing transcript content, with a backup first; preserve accurate historical provenance. Leave an unrepairable item `partial` and report the missing facts.

These are **structural checks**. They do not prove that media decodes, that transcript text is accurate, that a no-speech claim is true, that images exhaust the upstream carousel, that a person is correctly identified, or that a wiki synthesis is supported. Downloading still requires `ffprobe` checks; human/bot content review and citations are required separately. Concepts need ≥3 supporting sources unless explicitly requested; review concept support, person attribution/source links, contradictions, stale claims, broken wikilinks, tag quality, and watermarks separately. Search freshness and person-review coverage are reported separately from completion.
