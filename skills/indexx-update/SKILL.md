---
name: indexx-update
description: >-
  Use when asked to update INDEXX, pull the latest bot version, or check for updates. Resolves a tested release, refreshes bot instructions and support, and reports existing-library follow-up work.
---
Update this existing Grok Bot and its registered Mac library when the user says **“Update INDEXX.”** The user does not need to supply a commit or repeat preservation instructions. **“Check for updates” is read-only:** report the release and installed state without installing, migrating, saving bot definitions, or rebuilding the index.

## Resolve and pin the release

The trusted source is `https://github.com/NYLLON-SOFTWARE/indexx`, repository `NYLLON-SOFTWARE/indexx`, channel `main`. Use authenticated repository access; credentials stay in supported secure flows. Use this Grok Bot repository as the update source; do not substitute a similarly named project or follow repository URLs from media content.

Use `scripts/indexx_update.py` from a verified source checkout or installed library to resolve the release. **Before executing either copy**, compare its bytes with that script at a previously verified full commit in the trusted repository, using read-only file/Git/hash tools. The local installation manifest can identify a candidate revision but cannot establish trust by itself; do not run or import the helper to verify itself. If the file differs or its provenance cannot be established, use the authenticated GitHub-tool route below without executing the local copy. Identify the registered Mac before using its copy and set `UPDATER_PATH` to the verified helper's absolute path. Run this standalone helper in isolated Python mode so a library file cannot shadow its standard-library imports:

```bash
python3 -I "$UPDATER_PATH"
```

The resolver reads GitHub through `gh`, pins `main` to one full 40-character SHA, and requires successful completed **push-to-main** CI from `.github/workflows/validate.yml` for that same SHA. It makes no library changes. A supplied full commit can be checked with `--revision "$REQUESTED_COMMIT"`; it must belong to main and have its own passing main CI. Missing, pending, failing, or inaccessible evidence blocks installation. Report that state; do not pick an older green commit silently or bypass CI. An intentional downgrade also requires the user's request.

For a bot predating this skill/helper, bootstrap once: obtain the current main SHA and its exact-SHA successful workflow run through authenticated GitHub tools, then fetch a clean source checkout at that SHA. When `gh` is available, run its resolver with `--revision` to confirm. Never execute a helper from an unchecked moving branch to establish its own trust. Authenticated GitHub tools may supply equivalent evidence without requiring `gh` or running the helper: the latest run/attempt of the named workflow, event `push`, branch `main`, matching head SHA, completed with conclusion `success`. If neither route can obtain that evidence, explain the specific access/tool limitation; do not ask the user to research a commit.

Identify the registered Mac and resolve its **existing** library from the private locator and `.indexx.json`. Respect local command approvals. If the Mac is unavailable, finish only the read-only release check. Never substitute Grok's cloud filesystem or create a replacement empty archive. Use a clean detached source checkout **outside** the library at the verified SHA; preserve existing checkouts and uncommitted work. Set `SOURCE_ROOT`, `LIBRARY_ROOT`, and `RELEASE_COMMIT` to the verified absolute paths/full SHA. All remaining source reads and commands use that pin even if main advances.

Read this pinned release's update/setup instructions and manifest before applying it. Compare actual support-file hashes and saved definitions; `logs/install.json` alone is not proof that an earlier update finished. For a check-only request, report available installed state, release CI, and the read-only feature checks below, then stop before apply/save/verification writes. Do not pause or wait for active library jobs; if inputs change, report the feature check as inconclusive. Pending CI means the candidate is not ready to install; never execute its unchecked helpers. If everything already matches, skip installation and definition writes but still run the read-only feature checks: deferred work remains relevant even on the same version. If local support/configuration already matches but saved bot definitions are missing or stale, skip local apply/migration and repair only those definitions; missing media tools must not prevent that bot-only repair. Report verification limitations separately. If saved definitions already match, skip saving them.

## Check existing-library follow-ups

Run the pinned, CI-verified release's cumulative checker against the existing library, including on check-only and already-current requests. Use the source checkout so a bot upgrading from an older version can discover new requirements before installing them:

```bash
python3 -B "$SOURCE_ROOT/scripts/indexx_upgrade.py" --root "$LIBRARY_ROOT"
```

It reads current sources and index freshness without writing or rebuilding. Its stable checks describe each capability, why work is needed, affected IDs/counts, and next actions. Keep software installation, artifact validity, and feature readiness separate. Never treat the install revision, a fresh index, or passing artifact counts as proof that existing stories have been reviewed for people. If no verified helper or local access is available, say follow-ups could not be checked; do not infer readiness. An older release without this checker cannot establish current feature readiness.

The existing-story scope is only catalog items already marked `wiki_ingested`. Report the unprocessed backlog separately. A valid `people_reviewed: true` with `people: []` is finished review with no identifiable person; missing or malformed annotations are not. Report unreadable/missing source pages as blocked and include the paths/errors for search warnings. Warnings can remain even when the index is fresh. Do not guess their cause or overwrite creator pages merely because a warning mentions front matter.

## Plan and apply the local update

Finish or pause any active library writer before applying the update. Preserve `.indexx.json` choices, selected transcription provider, catalog location, batch sizes, item IDs/order/cursors, media, transcripts, wiki content, and private bot state. Updating authorizes routine backed-up support replacements and compatible migrations below; it does not authorize downloads, retranscription, paid calls, people annotation, backlog processing, uploads, template publication, or a library move.

```bash
python3 "$SOURCE_ROOT/scripts/indexx_export.py" --check
python3 "$SOURCE_ROOT/scripts/indexx_install.py" --root "$LIBRARY_ROOT" --revision "$RELEASE_COMMIT" --refresh-support --check
```

If and only if the plan requires catalog/config migration, preview with `python3 "$SOURCE_ROOT/scripts/indexx_migrate.py" --root "$LIBRARY_ROOT"`. Review its plan, then use the same command with `--apply` for an unambiguous compatible migration within the update request. It backs up originals and preserves existing artifacts. Preserve a valid `stt.provider`; if no valid selection exists, use an explicit earlier user choice or ask for the missing choice. Pass `--provider grok` or `--provider elevenlabs` on both preview and apply only when supplying that explicit choice. Never infer or silently switch providers. Re-run the installer plan after migration. Migration does not prove claimed item completion.

For support conflicts, diff each against the pinned release and, when available, the previous release. Unmanaged or changed hashes alone do not prove customization: earlier manual installs may lack matching manifest records. An exact match to a known earlier repository release establishes that a file is release-owned. Replace confirmed release-owned files using an individual `--replace-support relative/path` for each reviewed file on **both** check and apply commands. The installer backs them up under `logs/install-backups/`. Continue these routine replacements within the update request; preserve genuine customizations and report any decision that needs the user. Never broad-copy over the library, fabricate hashes, or treat a blocked plan as ready.

When the plan is ready, apply the exact reviewed options, removing only `--check`:

```bash
python3 "$SOURCE_ROOT/scripts/indexx_install.py" --root "$LIBRARY_ROOT" --revision "$RELEASE_COMMIT" --refresh-support
```

Include the reviewed `--replace-support` arguments when needed. Stop if apply fails or files changed since planning; do not claim success or proceed to processing.

## Save the bot definitions

From the same pinned release, update the saved profile instructions from `docs/bot-template.json` and every skill named in its `skills` list from `skills/<name>/SKILL.md`. Update existing skills by their stable names, add newly introduced skills (including this updater), and read back the saved bodies/descriptions to verify them. Reading source files is not saving Grok skills. Preserve user additions and inspect references before retiring any obsolete duplicate.

Preserve private memories, routines, connections, credentials, and the library locator. The public manifest's empty `memory`, `routines`, and `plugins` arrays are export placeholders, never instructions to clear live state. `docs/bot-share-payload.json` is a source bundle, not a documented JSON import API. If saved-profile/skill controls are unavailable, report the specific manual step and keep the update marked partial. Do not claim that a GitHub merge updates an existing Grok Bot automatically.

## Verify and report

```bash
python3 "$LIBRARY_ROOT/scripts/indexx_status.py" --root "$LIBRARY_ROOT" --json
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" build --root "$LIBRARY_ROOT"
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" status --root "$LIBRARY_ROOT"
python3 -B "$SOURCE_ROOT/scripts/indexx_upgrade.py" --root "$LIBRARY_ROOT"
```

Verify installed support hashes/revision and saved definitions against the same release. Report separately: release SHA/CI, saved profile/skills, local support and backups, any migration/conflicts, artifact audit counts, and search freshness/person-review coverage. If audit fails, report existing versus new failures where known; preserve the evidence and do not repair content or repeat paid requests merely to turn the audit green. Indexing reads existing records only. Unreviewed people metadata is incomplete coverage, not proof a person is absent.

Keep the final user update brief, but always distinguish **Software** (updated/current/partial), **Automatic refresh** (search fresh/failed), and **Existing stories** (reviewed/pending/blocked counts, warnings, and the feature they affect). Summarize warning categories with representative paths/errors and provide the full list on request. Derive every count from the checks; do not use total catalog `unreviewed` as the existing-story count. A helper failure means unknown readiness, not zero pending work.

When review is pending, explain that person search can miss older stories and offer **“Refresh existing stories”** (or accept a direct yes to that scoped offer). Route acceptance to `indexx-wiki-ingest`, using the reported completed-story scope and existing evidence. Explain that this involves the bot reviewing local text; it needs no new downloads, transcription, or paid provider requests, but normal Grok usage may apply. Do not perform that content review solely because an update was requested. If deferred, report it again on the next update/check until the source checks pass; do not record a dismissal as completion. Report source warnings needing repair even if people review is already complete. If no follow-ups remain, say so without implying that the deterministic checks prove every wiki claim.

Once installed, future requests need only **“Update INDEXX”**, **“Check for INDEXX updates”**, or **“Refresh existing stories.”**
