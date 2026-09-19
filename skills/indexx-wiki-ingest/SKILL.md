---
name: INDEXX wiki ingest
description: >-
  Use when compiling INDEXX wiki pages from transcribed (or image-only) items after media is local — including tags, facets, source/creator pages, and concepts only at ≥3 sources.
---
Compile wiki pages from transcript + info.json (+ optional poster frames).

## Produce / update

1. Source page `wiki/sources/instagram/{id}.md` — always
2. Creator page `wiki/entities/creators/{handle}.md` — first time for that handle
3. Tags (5–10 kebab-case) from `wiki/taxonomies/tags.md` — transcript + source front matter
4. Facets (orthogonal categories — `wiki/taxonomies/facets.md` / SCHEMA.md):
   - `form:` exactly one primary (`how-to` | `demo` | `sketch` | `quote` | `talk` | `review` | …)
   - `topic:` 1–3 subject domains
   - `intent:` exactly one (`entertainment` | `inspiration` | `reference` | `learn`)
5. Concepts `wiki/concepts/{slug}.md` — only when ≥3 sources share a theme, or user explicitly asks. `concepts:` front matter only links pages that exist. Never one concept per reel.
6. Collections only when obvious or asked
7. Update `wiki/index.md` + append `wiki/log.md`
8. Set catalog status → `wiki_ingested` only after SCHEMA completion checklist is green

## Supervision

First ~20 supervised (batches of 5–10). Never unattended 900.

## Done gate

Do not mark `wiki_ingested` until media + transcript (+ timestamps if speech) + tags + facets + wiki source page exist. Verify with `indexx-lint` / `scripts/indexx-status.sh`.
