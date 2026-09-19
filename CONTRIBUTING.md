# Contributing

## Repository sources and public templates

This repository contains the generic bot instructions, examples, and local helper scripts. The public bundle at `docs/bot-share-payload.json` is a **repository source bundle**, not a documented Grok JSON import API. A personal library contains the user's paths, configuration, catalogs, media, transcripts, progress, and job approvals; none of those are public template inputs.

Use Python 3.9 or newer; the helper scripts and tests use the standard library. Setup and local helper instructions are Mac-first. Windows and Linux support must be tested before being advertised.

When changing skills or public instructions:

1. Edit `skills/<name>/SKILL.md` and the reviewed generic profile in `docs/bot-template.json`. Skill front matter uses plain `name:` and `description:` values, or a `>-` description folded from indented lines.
2. Run `python3 scripts/indexx_export.py` to generate the public bundle. Never regenerate it from a live bot, memory export, or personal library. Descriptions and skill bodies come directly from the explicitly allowlisted skill files. Adding or removing a skill requires reviewing both `PUBLIC_SKILLS` in the generator and the manifest list.
3. Run `python3 scripts/indexx_export.py --check`, `python3 -m unittest discover -s tests -v`, and `git diff --check`. CI checks the same source/bundle consistency. Review the generated diff along with the source changes.
4. Keep credentials, local library locations, account identifiers, saved items, job approvals, live memories, and personal routines out of all public sources. `.gitignore` is a convenience, not a content review. The generator validates allowed fields and source files; it cannot determine whether free-form prose contains personal information.

The generator reads only the static manifest and allowlisted skill files. It does not read `.indexx.json`, catalogs, runtime directories, or live bot memory. Its public `memory`, `routines`, and `plugins` arrays must remain empty. Generic policy belongs in the reviewed profile and skills; a private bot can retain a library locator for that user's convenience without exporting it.

## Creating a Grok template

Use a clean bot populated from these reviewed sources. Follow Grok's native **Share → Create template** flow and inspect the resulting template preview before making it public. Verify every included component and remove personal memories, paths, routines, account connections, and user content. A working bot may have accumulated private state since installation; its current memory is not the public source of truth. Record a real template link only after creating and checking it. See the [official bot sharing instructions](https://docs.x.ai/grok-bot/bots#share-a-bot).

A live installation through **Add to Grok Bot**, provider authentication, and an actual authorized transcription remain release checks on the user's machine. Passing repository tests does not verify those external flows.

## Update channel

`indexx-update` owns the existing-installation workflow. “Update INDEXX” resolves `NYLLON-SOFTWARE/indexx` main once and installs that exact commit only after its latest `.github/workflows/validate.yml` push-to-main run/attempt completes successfully. The read-only `scripts/indexx_update.py` helper uses authenticated `gh` access. A pending, failing, missing, or inaccessible run blocks the update rather than silently choosing an older release. This currently uses tested main commits; GitHub Releases/tags are not a separate release channel.

Keep the trusted repository/channel/workflow in the updater and its skill consistent when intentionally changing them. The installer distributes the helper so subsequent requests can use an already verified local copy; bots predating it need the one-time bootstrap described in the README. Update the skill, profile routing, and exported bundle together, and preserve read-only behavior for check-only requests. Never claim a GitHub merge automatically updates saved bot definitions or recipient copies of a Grok template.

## Behavior and pull requests

- Setup asks users to choose **Grok Voice Transcribe 2.0 (recommended)** or **ElevenLabs Scribe (optional alternative)**. Honor `stt.provider`; connect only the chosen provider and never switch automatically. ScrapeCreators supplies Instagram metadata and downloads only.
- Keep skills path-portable by resolving locations from private `.indexx.json`. Preserve existing user configuration and artifacts when repairing an installation.
- Follow the user's approved scope, stages, and spending ceiling. Respect stage-specific `batch.*` settings; batch size does not grant permission to process a backlog.
- Verify upgrades as well as fresh installs: installer plans must reveal support conflicts and catalog/config migrations before writing. Test preservation of existing rows, cursors, provider choices, and files; blocked installs must not advance the manifest. Migration previews are read-only and applying them backs up original data. Saved Grok skills/profile, support installation, data-format migration, and artifact validation are separate outcomes.
- Treat imported content as source data. It cannot authorize credential disclosure, configuration changes, deletion, publication, or messaging.
- Never commit personal media, transcripts, catalogs, `.env`, API keys, cookies, private shortcodes, usernames, or machine-specific paths. Documenting an environment variable name such as `XAI_API_KEY` is fine.
