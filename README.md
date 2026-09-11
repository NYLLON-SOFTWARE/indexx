# Instagram Saved IDs

Export the IDs of your Instagram **Saved → All posts** grid using your agent's browser-extension sidebar, built-in browser, configured browser integration, or Computer Use. Select the skill, choose your authorized Instagram session, and ask it to collect your saved items.

**No Python, Node.js installation, terminal commands, or API keys are needed to use the skill.** It uses the host's available browser/computer tools and a small JavaScript helper for deduplication and export formatting. A browser extension is optional.

**Codex app:** [Add the INDEXX Instagram marketplace](#install-in-the-codex-app), then install **Instagram Saved IDs**.

## Use it from the sidebar

1. Install the skill in your agent using a supported route below.
2. Open Instagram and sign in in the browser connected to the extension.
3. Open the agent sidebar, select or mention **instagram-saved-ids**, and ask:

> Export all accessible saved-post IDs from my Instagram All posts grid. Include photos, carousels, videos, and reels. Give me JSON, CSV, and a plain text list, and tell me whether you reached the end.

The agent reads saved-grid links, scrolls for more items, deduplicates IDs, and returns the exports through the host's attachment, download, or file tools. It uses the account and tab you authorize; a username alone cannot grant access to another account's private Saved list.

To resume, provide the previous checkpoint. The agent re-traverses the grid and merges overlapping batches. Recovery across sessions requires the host to save a checkpoint; temporary session state alone cannot guarantee it.

## Use it without a browser extension

In a host with a built-in browser or enabled Computer Use, select the skill and ask:

> Use the browser or Computer Use to open my Instagram Saved All posts page and export the IDs. Use my existing signed-in browser if available; hand the page to me if I need to sign in.

- **Built-in or managed browser:** The agent opens Instagram in that browser. Its profile may need a separate sign-in. It uses available link/DOM inspection or visual controls. [ChatGPT browser documentation](https://learn.chatgpt.com/docs/browser).
- **Computer Use:** The agent operates the permitted browser app. If DOM/link inspection is unavailable, it opens each saved tile and reads the complete post URL through supported address-field or Copy link tools. This is slower and requires reliable text access; thumbnails cannot supply exact IDs. Computer Use must already be installed/enabled and permitted in the host. [ChatGPT Computer Use](https://learn.chatgpt.com/docs/computer-use).

Browser access, JavaScript processing, and file delivery are separate capabilities. The agent checks each before a long run. It returns the same JSON, CSV, and text outputs through whichever host file tools are available. If exact URLs or file delivery are unavailable, it explains the limitation and preserves usable progress. These fallback instructions have not yet been verified in a complete live Instagram run.

## What you get

| File | Contents |
| --- | --- |
| `saved-ids.txt` | One case-sensitive ID per line; normally Instagram URL shortcodes. |
| `saved-items.csv` | IDs, identifier kinds, observed media types, and URLs. |
| `saved-items.json` | Items, observed URL variants, capture interval, unresolved links, and coverage status. |

The skill collects exact links from Saved-grid items, including permalinks obtained by opening those items. It does not download media or convert shortcodes into numeric media IDs. A carousel's ID identifies its parent post, not each slide.

Coverage is explicit:

- **`partial`** — stopped because of a limit, challenge, error, or loading stall.
- **`end-observed`** — the accessible grid appeared exhausted after repeated settled checks. This is not a server-verified account total.
- **`empty`** — the page explicitly showed an empty Saved state.

Captures describe what was observed during a time interval. Unknown links and tiles without readable URLs are retained for review. If the host cannot create downloadable files, the agent can return copyable contents when they fit; it must report any delivery limitation instead of silently truncating an export.

## Compatibility

The shared workflow follows [Agent Skills](https://agentskills.io/specification); its outer package follows [Agent Plugins 1.0.0](https://agent-plugins.org/). These conventions let compatible hosts load the same skill. The host's agent executes the workflow using its available tools.

The host needs authenticated browser control, exact URL capture, JavaScript data processing, and checkpoint/export tools. The skill selects among available extension, browser, and Computer Use routes. OpenAI also documents side chat beside the current page through its [browser extension](https://learn.chatgpt.com/docs/chrome-extension).

The same skill can be installed in Codex, Cursor, OpenClaw, Claude Code, and other Agent Skills hosts with equivalent browser capabilities. Their setup and skill-selection UI differ. Format support does not establish a completed live Instagram test in every product; see the [source-linked research](docs/skill-portability-research.md).

## Installation routes

Use the host's skill installer/import flow with the **whole** `skills/instagram-saved-ids/` folder. This repository distributes a skill for existing agent browser/computer tools; it does not bundle a new browser extension.

### Install in the Codex app

This repository is a custom Codex marketplace. No server deployment or public directory submission is needed for this installation route. OpenAI documents [repository marketplaces](https://developers.openai.com/plugins/build/plugins#build-your-own-curated-plugin-list); the catalog uses the same root-plugin layout as [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin/blob/main/.agents/plugins/marketplace.json).

1. Open **Plugins** from the Codex sidebar.
2. Click the arrow next to **Create**, then select **Add marketplace**.
3. Enter these values:

   | Field | Value |
   | --- | --- |
   | Source | `NYLLON-SOFTWARE/indexx-instagram-skill` |
   | Git ref | `main` |
   | Sparse paths | Leave blank |

4. Click **Add marketplace**.
5. Select **INDEXX Instagram** or search for **Instagram Saved IDs**, then install **indexx-instagram-skill**.
6. Start a new conversation and select **instagram-saved-ids**. If it does not appear, restart the app.

Adding the marketplace makes the plugin available; installing the plugin activates its bundled skill. Browser or Computer Use access still comes from your configured host tools.

**Private repository:** This repository is currently private. You need GitHub read access and working Git authentication on the computer running Codex. If the source cannot be fetched, verify repository access and GitHub organization authorization. A custom marketplace does not grant access to a private repository.

### Codex CLI (optional)

If you use the CLI, register the same marketplace and install its plugin:

```sh
codex plugin marketplace add NYLLON-SOFTWARE/indexx-instagram-skill --ref main
codex plugin add indexx-instagram-skill@indexx-instagram-skill
```

The identifier before `@` is the plugin name; the identifier after it is the marketplace name. Start a new session after installation. These commands are an alternative to the app steps above.

To refresh this marketplace after a new release, run `codex plugin marketplace upgrade indexx-instagram-skill`, then reinstall/update the plugin from **Plugins** and start a new conversation.

### ChatGPT and standalone skills

OpenAI documents standalone skills in the ChatGPT desktop app, Codex CLI, and IDE extension. Plugin-bundled skills also work in Chat and Work across ChatGPT web, desktop, and mobile. Select a skill with `@` in ChatGPT; in Codex CLI/IDE use `$instagram-saved-ids`. Availability of the installed skill in a browser session depends on the host's integration. [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills).

The package includes portable `plugin.json`, OpenAI compatibility metadata at `.codex-plugin/plugin.json`, and the repository marketplace at `.agents/plugins/marketplace.json`. Workspace admins can also [import the GitHub marketplace](https://learn.chatgpt.com/docs/enterprise/plugin-management) for their members; workspace access and installation policies apply.

A public GitHub repository is not a ChatGPT directory listing. Public directory distribution requires a separate submission, review, and publication. This project has not been submitted. [OpenAI publishing process](https://developers.openai.com/plugins/deploy/submission).

### Other hosts and developer installation

For a manual install, copy `skills/instagram-saved-ids/` into a supported discovery directory, preserving its name and contents:

| Agent | Project/workspace skills directory | Personal skills directory |
| --- | --- | --- |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `.agents/skills/` | `~/.agents/skills/` |
| [Cursor](https://cursor.com/docs/skills) | `.cursor/skills/` or `.agents/skills/` | `~/.cursor/skills/` |
| [OpenClaw](https://docs.openclaw.ai/tools/skills) | `<workspace>/skills/` | `~/.openclaw/skills/` with default state directory |
| [Claude Code](https://code.claude.com/docs/en/skills) | `.claude/skills/` | `~/.claude/skills/` |
| [GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) | `.github/skills/` | `~/.copilot/skills/` |
| [Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/) | `.gemini/skills/` | `~/.gemini/skills/` |
| [OpenCode](https://opencode.ai/docs/skills/) | `.opencode/skills/` | `~/.config/opencode/skills/` |

For developers who already use npm, the optional [skills CLI](https://github.com/vercel-labs/skills) automates that installation:

```sh
npx skills add NYLLON-SOFTWARE/indexx-instagram-skill \
  --skill instagram-saved-ids \
  -a codex -a cursor -a claude-code -a openclaw --copy
```

Keep only the targets you use; add `--global` for personal installation. This is an optional installation route, not a command the browser-skill user runs for each export. Refresh skills if the entry does not appear. OpenClaw's native local installer should receive the skill subdirectory, not this repository's plugin root.

## How it is packaged

```text
.agents/plugins/marketplace.json     Codex marketplace pointing to this plugin
plugin.json                          Portable Agent Plugins manifest
.codex-plugin/plugin.json            OpenAI compatibility metadata
skills/instagram-saved-ids/
  SKILL.md                           Shared browser workflow
  agents/openai.yaml                 Optional OpenAI display metadata
  references/                        Collection and runtime guidance
  scripts/export_ids.js              Pure JavaScript; no imports or network
examples/checkpoints.jsonl           Synthetic example
docs/skill-portability-research.md   Source-linked compatibility research
scripts/                            Developer-only utilities
tests/                              Data handling and packaging checks
```

The JavaScript helper accepts captured batch objects and returns normalized records plus the text contents of the three files. The host's artifact/download tools deliver those contents. It does not open a shell, access the filesystem, or install packages.

## Developer checks

The following commands are for maintainers, not browser-skill users. All development tooling uses Node.js 22+ and npm. The installed browser skill has no package dependencies.

```sh
npm ci --ignore-scripts
npm test
npm run validate
npm run build
```

The builder creates `dist/instagram-saved-ids-0.1.0.zip` for individual-skill import and `dist/indexx-instagram-skill-0.1.0.zip` for plugin distribution. Import support depends on the host. Explicit file allowlists exclude development utilities, npm packages, private checkpoints, exports, tests, and Git history from both packages.

GitHub Actions checks the skill's frontmatter and relative resources against the Agent Skills specification, validates the plugin against its published JSON Schema, checks the marketplace's source and plugin identity, and tests JavaScript and package behavior on Linux, macOS, and Windows. The export helper is tested in an isolated runtime without Node/DOM/network APIs. An isolated skills CLI installation has also verified the distribution layout for Codex, Cursor, Claude Code, and OpenClaw. Live browser testing remains separate from those checks.

## Privacy

The skill requests no cookies, tokens, or API credentials and adds no remote collection server or telemetry. Your selected agent/browser provider still handles data according to its own settings. Keep private captures out of commits, issues, and shared logs. Examples and tests use synthetic data. This project is not affiliated with Instagram or Meta.
