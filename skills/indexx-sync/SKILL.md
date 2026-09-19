---
name: INDEXX sync
description: >-
  Use when starting or ending a file-touching INDEXX run that needs Mac canonical markdown and the cloud /workspace/INDEXX working copy kept in sync (never media).
---
Sync **markdown only** between Mac canonical INDEXX root and `/workspace/INDEXX`.

## Allowed
`catalog/`, `markdown/`, `wiki/`, `logs/`, `AGENTS.md`, `SCHEMA.md`, `.indexx.json`, `README.md`

## Forbidden
Anything under `media/` (and raw bytes anywhere). Never overwrite Mac with an older cloud copy without asking.

## Status
Scaffold stub. Implement when the user specifies the Mac↔Bot sync mechanism. Until then, treat Mac paths via registered-machine tools as canonical and do not invent a sync.
