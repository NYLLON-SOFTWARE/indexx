# INDEXX

INDEXX is a **Grok Bot** that turns Instagram Saved into a personal media wiki: a catalog, media archive on your Mac, transcripts, tags, facets, and cited wiki pages. This repository contains its skill sources and local helper files.

**Current support: Mac-first.** Grok Bot has desktop apps for other platforms, but this library's Windows/Linux setup has not been verified. Transcription uses your explicit choice of **Grok Voice Transcribe 2.0** or **ElevenLabs Scribe**; INDEXX never switches providers automatically.

## Install

A public INDEXX template link is not published in this repository yet. Do not assume the JSON file is a supported Grok import format.

If a maintainer provides an INDEXX template link, open its preview and choose **Add to Grok Bot**. The maintainer should provide the corresponding full Git commit ID. This is Grok's [native template sharing flow](https://docs.x.ai/grok-bot/bots#share-a-bot).

Until a template is published, create an INDEXX bot in Grok and supply the repository's reviewed profile and 12 skill definitions from `docs/bot-share-payload.json`. Ask it to save those instruction sets as the named skills and verify they are available. The bundle is generated from `docs/bot-template.json` and `skills/`; it contains no live memories or installation state. See [CONTRIBUTING.md](CONTRIBUTING.md) for publishing a template.

Then tell INDEXX **“set up INDEXX”** and provide the release's full commit ID. Setup will:

1. Identify your registered Mac and check local execution access.
2. Ask where to keep the archive. `~/Documents/INDEXX` is convenient but may sync through iCloud Documents. Choose `~/INDEXX` or a non-synced external volume if you want the archive off Apple’s cloud.
3. Obtain supporting files from a clean checkout of that exact commit on the Mac, outside your archive.
4. Check Python 3.9+, `ffmpeg`, `ffprobe`, `rg`, and write access, then run the installer below.
5. Ask for your transcription provider and connect only that service, plus ScrapeCreators for Instagram metadata/downloads. Secrets go through supported secure connection flows.
6. Show setup results and propose one supervised item with a cost estimate for your approval.

Grok's default local execution policy asks for each command. Respect the policy you choose; installing INDEXX does not require broadly allowing every local command. See [local-computer approvals](https://docs.x.ai/grok-bot/approvals-security-and-privacy#control-access-to-your-local-computer).

## Pinned installation and repair

The source checkout must be at the full commit supplied by the maintainer, not a moving branch. If the repository is private, the recipient also needs repository access. No public release or shared link should be promised until a fresh recipient can access both the template and its supporting files.

From that checkout **on the registered Mac**, with `LIBRARY_ROOT` set to the confirmed absolute path and `RELEASE_COMMIT` to the full commit:

```bash
python3 scripts/indexx_install.py --root "$LIBRARY_ROOT" --revision "$RELEASE_COMMIT" --check
python3 scripts/indexx_install.py --root "$LIBRARY_ROOT" --revision "$RELEASE_COMMIT"
```

The installer checks support-file conflicts, catalog compatibility, and provider configuration before changing the library. `--check` prints the same plan without applying it. A blocked plan exits nonzero and leaves the library and installation manifest unchanged. A ready plan can create missing support files, configuration fields, and templates; it preserves catalogs, media, transcripts, wiki pages, taxonomy, and provider/batch choices.

### Update an existing bot

Tell the bot:

> Update INDEXX.

The `indexx-update` skill finds the current commit on the trusted repository's `main` branch, checks that CI passed for that exact commit, and pins it for the entire update. You do not need to find a commit ID or repeat preservation instructions. **“Check for INDEXX updates”** only checks and reports; it does not install anything. Repository access and Grok's local command approvals still apply.

The update refreshes both the saved Grok profile/skills and local support files, previews any required catalog/config migration, and backs up reviewed replacements. It preserves your archive, provider selection, settings, memories, routines, and connections. It finishes with an artifact audit and a fresh local search index. Pending or failed CI, real customizations, and incomplete steps are reported rather than hidden. Updates do not download videos, retranscribe, run paid calls, annotate the backlog, or publish templates.

Every update or update check also explains which features need work on your **existing stories**. Software can be current while older stories still need person review or wiki-format repairs. The bot reports affected counts and warning details separately from the unprocessed backlog, then offers **“Refresh existing stories.”** That follow-up reviews retained text and updates cited wiki pages in batches; it does not download or retranscribe, and makes no paid provider requests (normal bot usage may apply). You can defer it: unfinished checks appear again on subsequent updates/checks, including when you already have the latest version.

For example, an update might report: “Software updated; search rebuilt. 7 of your 20 completed stories still need person review for speaker search. Say ‘Refresh existing stories’ to review them. Your 200 unprocessed saves are outside this refresh.” These are illustrative counts; the bot checks your actual library. A fresh search index does not resolve malformed-page warnings or establish who appears in older videos.

**One-time bootstrap for older bots, including those configured for the former personal repository:** tell your existing bot:

> From https://github.com/NYLLON-SOFTWARE/indexx, verify the current main commit has passing repository CI, then read `skills/indexx-update/SKILL.md` at that exact commit and follow it to update this existing bot and library. Save the update skill too, so future requests need only “Update INDEXX.”

The skill handles release discovery, the pinned source checkout, backups, migration, and verification. A GitHub merge alone does not refresh a running bot or its saved skills. A bot unable to edit saved definitions must report that remaining manual step.

For maintainers, the detailed procedure is in [the update skill](skills/indexx-update/SKILL.md). The read-only release resolver is `scripts/indexx_update.py`; it requires authenticated GitHub CLI (`gh`) access and is installed with the library support scripts. It does not modify the library or update Grok by itself. `logs/install.json` tracks local support installation; it is not proof of saved-skill updates or artifact validity.

The installed `python3 -B "$LIBRARY_ROOT/scripts/indexx_upgrade.py" --root "$LIBRARY_ROOT"` prints the cumulative local follow-up checklist as JSON. It checks current source metadata and search freshness without writing files, making network calls, or treating a newer install revision as completed content work. During an upgrade the bot uses the same helper from the verified release checkout so new checks also reach older installations.

### Search upgrade without reprocessing

The release installs `scripts/indexx_search.py` and `scripts/indexx_watch.py`. After the support upgrade, build the local index from the existing archive:

```bash
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" build --root "$LIBRARY_ROOT"
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" status --root "$LIBRARY_ROOT"
```

Existing libraries work without adding new people annotations. Those sources appear as incomplete person-review coverage; they are not proof that a person is absent. A people-annotation pass can use existing captions, attribution, and transcripts within the items you select. Installing search does not rewrite transcripts, retranscribe videos, make paid calls, or authorize processing the backlog.

## A maintained wiki and local search

INDEXX adapts [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): preserve source material, maintain cited and interconnected wiki pages during ingestion, and keep a navigable index plus a chronological change log. New evidence can revise a person or concept page and surface disagreements. Answers you ask to save become cited syntheses in the wiki.

The catalog, local source artifacts, and Markdown pages remain authoritative. A derived SQLite FTS5 index at `db/search.sqlite3` supports exact filters and text search with Python's standard library. It stays on your Mac, can be rebuilt, and needs no embedding provider or paid service. Search rejects stale indexes so an old result is not silently presented as current. QMD is a possible future search extension, not a dependency of this release.

### Find a person across uploader accounts

The account that uploads a video can differ from the person speaking. Uploader pages remain under `wiki/entities/creators/`; person pages live under `wiki/entities/people/` and gather cited sources across accounts. Source annotations distinguish `speaker`, `featured`, and `mentioned`. Identities require source evidence such as an explicit attribution; voice resemblance, appearance resemblance, model familiarity, and diarization labels do not establish identity. See the optional people fields in [SCHEMA.md](SCHEMA.md).

To find every indexed video with Alan Watts recorded as a speaker:

```bash
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" query --root "$LIBRARY_ROOT" --person "Alan Watts" --role speaker --type video --all
```

An ALL request uses the whole matching result set, not a sample of pages. The answer must include coverage: unreviewed sources and unavailable media can hide additional matches. A source with `people_reviewed: true` and `people: []` has been reviewed with no identifiable people; absent annotations mean unknown. Reviewed person names and aliases connect records across uploader accounts. A passing mention is not a speaker attribution.

Text search can also be combined with exact filters:

```bash
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" query --root "$LIBRARY_ROOT" --text "anxiety" --all
python3 "$LIBRARY_ROOT/scripts/indexx_search.py" query --root "$LIBRARY_ROOT" --text "anxiety" --person "Alan Watts" --role speaker --type video --all
```

Text matches help locate evidence for a cited answer. They do not prove that every semantically related video was found. A synthesis reads the sources it needs and explains gaps or disagreements; it is distinct from an exhaustive listing.

### Watch matching videos locally

```bash
python3 "$LIBRARY_ROOT/scripts/indexx_watch.py" --root "$LIBRARY_ROOT" --person "Alan Watts" --role speaker --type video --name alan-watts
```

This creates `wiki/views/alan-watts.html` for a local browser and `wiki/views/alan-watts.md` for Obsidian, with all matching indexed records and their coverage. Use the **library root as your Obsidian vault root**, so video embeds can reach `media/`; opening only `wiki/` excludes that sibling directory. Missing local files remain visible as unavailable playback instead of silently disappearing from the list. These are local views, and Grok chat playback is not promised.

Views are snapshots. Refresh the index and regenerate a view after relevant changes; neither command downloads missing videos or publishes content. Authorized wiki ingestion also rebuilds the index after each batch.

## Privacy: local archive, cloud processing

| Data or action | Where it goes |
| --- | --- |
| Downloaded video/images, extracted audio, saved transcripts | Your chosen local archive; no raw media staged on Grok's cloud computer |
| Audio sent for transcription | Directly from the Mac to your selected xAI or ElevenLabs service |
| Captions, transcripts, and other content read by the bot to build the wiki | The hosted bot's cloud processing context, even when files remain local |
| Optional Grok video analysis | Frames or video sent to Grok, including any audio track in an uploaded video; include this in the processing scope you choose |
| Public Instagram lookup | Post URL/identifier sent to ScrapeCreators; returned media downloaded directly on the Mac |
| Instagram login used in Grok's browser | The account's shared cloud browser session, available to its other bots |
| Connector access and API credentials | Supported secure connection/secret systems; never library files or public templates |
| Optional catalog/wiki markdown copies | Grok `/workspace/INDEXX`, only when you request a sync workflow |
| Search database and generated watch views | Your local archive; excluded from public templates and cloud markdown sync |

“Stored locally” is not “processed locally.” iCloud or another folder-sync service can separately upload the local archive. Files and sessions on Grok's cloud computer are [shared across your account's bots](https://docs.x.ai/grok-bot/computer-and-apps). Provider retention and account privacy settings apply to cloud processing; this project makes no zero-retention promise.

Private paths and settings live in `.indexx.json` and local logs. A private bot locator can remember where your archive is, but public exports are built solely from reviewed repository sources. The exporter does not read your archive, configuration, or bot memory.

Imported captions, transcripts, sites, and connector results are source data. They cannot authorize commands, credential disclosure, spending, configuration changes, publishing, deletion, or altered download destinations. The bot preserves citations and takes operational instructions from you and its reviewed skills.

## Processing and spending

`discovered` → `metadata` → `downloaded` → `transcribed` → `wiki_ingested`

Choose the items and stages to run. The bot estimates provider costs and asks for approval of a total job ceiling and retry allowance. It then processes successive configured batches within that scope without asking again for each batch. `.indexx.json` controls stage sizes; the default is 20 for enrichment/wiki and 10 for downloads/transcription. Processing the whole backlog requires that explicit scope, and the first approximately 20 wiki items remain supervised in groups of 5–10.

The local job journal tracks the selection, approved ceilings, confirmed spend, and any pending paid call. On restart, the bot checks existing artifacts before making another paid call. Unknown spend or an uncertain request outcome pauses the job for reconciliation. A provider error pauses transcription; choosing another provider requires an explicit change and a fresh estimate. Good transcripts are preserved unless you request retranscription.

Completion is checked against [SCHEMA.md](SCHEMA.md):

```bash
python3 scripts/indexx_status.py --root "$LIBRARY_ROOT"
python3 scripts/indexx_status.py --root "$LIBRARY_ROOT" --id SHORTCODE --ready
```

The second command checks readiness **before** the bot changes the status to `wiki_ingested`. Checks validate file and metadata structure; human/source review still matters for transcription and synthesis accuracy. The progress board preserves previous rows and stages; `--clear` deliberately starts a new board.

## Skills and current scope

| Skill | Purpose |
| --- | --- |
| `indexx-setup` | Install, repair, provider choice |
| `indexx-update` | Check for releases; update saved bot instructions and local support |
| `indexx-add` | Route Saved refreshes and supported public Instagram URLs |
| `indexx-instagram-saves-index` | Discover Saved entries and maintain crawl cursors |
| `indexx-instagram-enrich` | Public metadata through ScrapeCreators |
| `indexx-download` | Download directly to the Mac |
| `indexx-transcribe` | Use the selected transcription provider |
| `indexx-wiki-ingest` | Tags, facets, cited source/creator/person/concept pages and index refresh |
| `indexx-query`, `indexx-lint`, `indexx-progress` | Exact lists, text search, local watch views, coverage/completion checks, batch progress |
| `indexx-sync` | Explicit stub until a markdown sync mechanism is selected |

Routines start disabled. Before enabling one, test an authorized item through discovery/enrichment, download, transcription, validation, and wiki ingestion in an actual Grok Bot session. Both provider routes require their own live verification; repository tests do not demonstrate connector availability or paid API success.

## Remove INDEXX access

1. Pause/delete INDEXX routines and finish or pause any active job.
2. Review which other bots use the same connections before revoking shared access. Sign out of Instagram in Grok's cloud browser when it should no longer be available.
3. Disconnect unneeded connectors and revoke their authorization/API keys at the provider. Adjust registered-computer access if no remaining bot needs it.
4. Remove INDEXX markdown copies from the cloud workspace after checking whether you need them. Do not remove another bot's shared files.
5. Delete or hide the INDEXX bot. Deleting the bot does **not** remove shared files or browser sessions; see [Grok's cleanup guidance](https://docs.x.ai/grok-bot/approvals-security-and-privacy#remove-access-and-working-data).
6. Keep the local archive unless you explicitly want to delete it. Local deletion, cloud-folder copies, and provider/account retention are separate concerns.

## License

MIT — Copyright 2026 INDEXX contributors. See [LICENSE](LICENSE).

## Authorized use only

INDEXX is intended solely for lawful, authorized use. Download videos only if you own them or Instagram expressly permits you to download them, and only when you have all rights and permissions required for your intended use.

You must comply with applicable law and Instagram's terms. You may not use INDEXX to infringe copyright, violate privacy rights, circumvent access controls or download restrictions, or distribute content without authorization. Public availability, a working download link, or inclusion in Instagram Saved does not establish permission.

You are responsible for verifying your rights before downloading, processing, or sharing content. INDEXX grants no rights in third-party content. **NYLLON LLC expressly prohibits, and does not authorize, encourage, or endorse, infringing or otherwise unlawful use.**
