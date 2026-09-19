---
name: INDEXX progress
description: >-
  Use during multi-item INDEXX jobs to update logs/pipeline-progress.md without losing previous rows or stage results.
---
Keep a local progress board for the currently approved job. Resolve the confirmed Mac library root from `.indexx.json`.

## Update the board

```bash
python3 scripts/indexx_progress.py --root "$ROOT" --title "Selected saves" \
  --row 'id=SHORTCODE handle=example watch=running note="Checking for speech"'
python3 scripts/indexx_progress.py --root "$ROOT" \
  --row 'id=SHORTCODE watch=done note="Visual check complete"'
```

Rows merge by `id`; omitted rows, fields, stage results and title are preserved. Quote values containing spaces inside each `--row` argument. Text is escaped for the Markdown table. Invalid input fails without replacing the existing board. Use `--clear` only when explicitly starting a new job; resuming the same job must not clear progress.

`logs/pipeline-progress.json` stores progress; `logs/pipeline-progress.md` is its rendered view. Both are written atomically. If writing the view is interrupted, rerun the command to rebuild it from JSON. The first update migrates an existing Markdown-only board. Legacy `✗` cannot distinguish failure from skip and is conservatively migrated as failure. Corrupt state is reported, not silently discarded. Timestamps use the local computer's timezone. Progress paths must resolve inside the confirmed library, including when clearing a board.

Allow only one job writer per library at a time. Coordinate between bots before updating the shared local job journal or progress board; atomic file replacement does not merge concurrent writers.

## Stages and states

- Stages: `dl` download, `aud` audio, `watch` optional visual check, `stt` selected-provider transcription, `tags` tags/facets, `wiki` wiki ingest.
- States: `pending` ○, `running` …, `done` ✓, `fail` ✗, `skip` −. Use an explanatory note for failed/skipped work.

At stage gates update affected rows and send a short chat update when progress or a blocker is meaningful. At job end share the final board. The board is a display, not evidence of completion or spending authority: validate artifacts using `indexx-lint`, and resume from the bounded `logs/job.json` contract in `AGENTS.md`.

## Scope and spending

Use `.indexx.json` `batch.*` for scheduling within the approved items and stages. Never expand a selected job to the whole backlog. Preserve completed work on retries. Before paid calls follow the shared job approval, reservation and reconciliation rules; an existing approval covers further batches only within its provider, scope and remaining ceilings. Never switch transcription providers automatically.
