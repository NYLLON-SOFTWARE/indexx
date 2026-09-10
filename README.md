# Instagram Saved IDs

Export the IDs of your Instagram **Saved → All posts** grid from your agent's browser-extension sidebar. Select the skill, point it at your signed-in Instagram tab, and ask it to collect your saved items.

**No Python, Node.js installation, terminal commands, or API keys are needed to use the skill.** It uses the browser extension's existing tools and a small JavaScript helper for deduplication and export formatting.

## Use it from the sidebar

1. Install the skill in your agent using a supported route below.
2. Open Instagram and sign in in the browser connected to the extension.
3. Open the agent sidebar, select or mention **instagram-saved-ids**, and ask:

> Export all accessible saved-post IDs from my Instagram All posts grid. Include photos, carousels, videos, and reels. Give me JSON, CSV, and a plain text list, and tell me whether you reached the end.

The agent reads saved-grid links, scrolls for more items, deduplicates IDs, and returns the exports through the extension's download/artifact tools. It uses the account and tab you authorize; a username alone cannot grant access to another account's private Saved list.

To resume, provide the previous checkpoint. The agent re-traverses the grid and merges overlapping batches. Recovery across sessions requires the host to save a checkpoint; temporary session state alone cannot guarantee it.

## What you get

| File | Contents |
| --- | --- |
| `saved-ids.txt` | One case-sensitive ID per line; normally Instagram URL shortcodes. |
| `saved-items.csv` | IDs, identifier kinds, observed media types, and URLs. |
| `saved-items.json` | Items, observed URL variants, capture interval, unresolved links, and coverage status. |

The skill collects rendered links. It does not download media or convert shortcodes into numeric media IDs. A carousel's ID identifies its parent post, not each slide.

Coverage is explicit:

- **`partial`** — stopped because of a limit, challenge, error, or loading stall.
- **`end-observed`** — the accessible grid appeared exhausted after repeated settled checks. This is not a server-verified account total.
- **`empty`** — the page explicitly showed an empty Saved state.

Captures describe what was observed during a time interval. Unknown links are retained for review. If the extension cannot create downloadable files, the agent can return copyable contents when they fit; it must report any delivery limitation instead of silently truncating an export.

## Compatibility

The shared workflow follows [Agent Skills](https://agentskills.io/specification); its outer package follows [Agent Plugins 1.0.0](https://agent-plugins.org/). These conventions let compatible hosts load the same skill. The sidebar's agent executes the workflow using its tools; `SKILL.md` is not a standalone extension executable.

The host needs authenticated tab control, rendered link inspection, JavaScript data processing, and checkpoint/export tools. OpenAI documents side chat beside the current page and browser control through its [browser extension](https://learn.chatgpt.com/docs/chrome-extension).

The same skill can be installed in Codex, Cursor, OpenClaw, Claude Code, and other Agent Skills hosts with equivalent browser capabilities. Their setup and skill-selection UI differ. Format support does not establish a completed live Instagram test in every product; see the [source-linked research](docs/skill-portability-research.md).

## Installation routes

Use the host's skill installer/import flow with the **whole** `skills/instagram-saved-ids/` folder. This repository distributes a skill for existing agent extensions; it does not bundle a new browser extension.

### ChatGPT and Codex

OpenAI documents standalone skills in the ChatGPT desktop app, Codex CLI, and IDE extension. Plugin-bundled skills also work in Chat and Work across ChatGPT web, desktop, and mobile. Select a skill with `@` in ChatGPT; in Codex CLI/IDE use `$instagram-saved-ids`. Availability of the installed skill in a browser session depends on the host's integration. [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills).

For local plugin testing, ask `@plugin-creator` in ChatGPT Work or `$plugin-creator` in Codex to add the cloned plugin folder to your personal local marketplace. Install it from the desktop Plugins Directory and test it in a new conversation. The package includes portable `plugin.json` and OpenAI compatibility metadata at `.codex-plugin/plugin.json`. [Plugin setup](https://learn.chatgpt.com/docs/build-plugins), [package format](https://developers.openai.com/plugins/build/plugins).

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

GitHub Actions checks the skill's frontmatter and relative resources against the Agent Skills specification, validates the plugin against its published JSON Schema, and tests JavaScript and package behavior on Linux, macOS, and Windows. The export helper is tested in an isolated runtime without Node/DOM/network APIs. An isolated skills CLI installation has also verified the distribution layout for Codex, Cursor, Claude Code, and OpenClaw. Live browser testing remains separate from those checks.

## Privacy

The skill requests no cookies, tokens, or API credentials and adds no remote collection server or telemetry. Your selected agent/browser provider still handles data according to its own settings. Keep private captures out of commits, issues, and shared logs. Examples and tests use synthetic data. This project is not affiliated with Instagram or Meta.
