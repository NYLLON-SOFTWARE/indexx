# INDEXX

INDEXX is a **Grok Bot** that turns Instagram Saved into a personal media wiki: a catalog, media archive on your Mac, transcripts, tags, facets, and cited wiki pages. This repository contains its skill sources and local helper files.

**Current support: Mac-first.** Grok Bot has desktop apps for other platforms, but this library's Windows/Linux setup has not been verified. Transcription uses your explicit choice of **Grok Voice Transcribe 2.0** or **ElevenLabs Scribe**; INDEXX never switches providers automatically.

## Install

A public INDEXX template link is not published in this repository yet. Do not assume the JSON file is a supported Grok import format.

If a maintainer provides an INDEXX template link, open its preview and choose **Add to Grok Bot**. The maintainer should provide the corresponding full Git commit ID. This is Grok's [native template sharing flow](https://docs.x.ai/grok-bot/bots#share-a-bot).

Until a template is published, create an INDEXX bot in Grok and supply the repository's reviewed profile and 11 skill definitions from `docs/bot-share-payload.json`. Ask it to save those instruction sets as the named skills and verify they are available. The bundle is generated from `docs/bot-template.json` and `skills/`; it contains no live memories or installation state. See [CONTRIBUTING.md](CONTRIBUTING.md) for publishing a template.

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

The installer copies the local helpers, schema, instructions, catalog stub, and wiki templates. Running it again repairs missing files and fills missing configuration fields. Existing catalog entries, media, transcripts, wiki pages, taxonomy, and provider/batch choices are preserved.

For a requested upgrade, use `--refresh-support`. The installer replaces only previously managed support files that have not been customized, and reports other differences for review. Per-file hashes and source revision are recorded locally in `logs/install.json`. A library move is a separate operation; setup will not silently repoint an existing config.

## Privacy: local archive, cloud processing

| Data or action | Where it goes |
| --- | --- |
| Downloaded video/images, extracted audio, saved transcripts | Your chosen local archive; no raw media staged on Grok's cloud computer |
| Audio sent for transcription | Directly from the Mac to your selected xAI or ElevenLabs service |
| Captions, transcripts, and other content read by the bot to build the wiki | The hosted bot's cloud processing context, even when files remain local |
| Optional Grok video analysis | Visual content sent to Grok; include this in the processing scope you choose |
| Public Instagram lookup | Post URL/identifier sent to ScrapeCreators; returned media downloaded directly on the Mac |
| Instagram login used in Grok's browser | The account's shared cloud browser session, available to its other bots |
| Connector access and API credentials | Supported secure connection/secret systems; never library files or public templates |
| Optional catalog/wiki markdown copies | Grok `/workspace/INDEXX`, only when you request a sync workflow |

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
| `indexx-add` | Route Saved refreshes and supported public Instagram URLs |
| `indexx-instagram-saves-index` | Discover Saved entries and maintain crawl cursors |
| `indexx-instagram-enrich` | Public metadata through ScrapeCreators |
| `indexx-download` | Download directly to the Mac |
| `indexx-transcribe` | Use the selected transcription provider |
| `indexx-wiki-ingest` | Tags, facets, cited source/creator/concept pages |
| `indexx-query`, `indexx-lint`, `indexx-progress` | Search, completion checks, batch progress |
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
