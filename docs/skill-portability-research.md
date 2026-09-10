# Skill portability research

Researched: **2026-09-09**. Sources are first-party documentation checked on that date. Product support and installation paths can change. These findings establish documented compatibility, not a completed Instagram export test in every client. Installation and the browser-sidebar user workflow are covered in the [README](../README.md).

## Recommendation

Use **Agent Skills** for the skill itself and **Agent Plugins 1.0.0** for a portable outer package. Publish one canonical `instagram-saved-ids` skill directory and document how each host installs it. Agent Skills is a format for reusable instructions and resources; adopting it does not make authenticated browser access, JavaScript processing, or artifact delivery appear in a host that lacks them. The standard's own implementation guide separates discovery, activation, and resource access, and leaves these mechanisms to the host. [Agent Skills overview](https://agentskills.io/home), [client implementation guide](https://agentskills.io/client-implementation/adding-skills-support).

For this exporter, the correct claim is: **portable skill instructions and a JavaScript normalizer, usable by a compatible agent with the required browser and file capabilities**. Do not claim universal execution across all chat products or all OpenClaw-like agents.

## Shared package contract

The specification requires a `SKILL.md` with YAML frontmatter and a Markdown body. Required fields are `name` and `description`. The name must match its directory, use lowercase letters/numbers and single hyphens, and fit within 64 characters. The description has a 1,024-character limit. Optional fields are `license`, `compatibility`, `metadata`, and experimental `allowed-tools`; metadata is a string-to-string mapping. The specification recommends fewer than 500 lines, relative resource links, and optional `scripts/`, `references/`, and `assets/` directories. Script runtime support depends on the host. [Agent Skills specification](https://agentskills.io/specification).

Recommended repository shape:

```text
README.md
LICENSE
plugin.json
docs/
skills/
  instagram-saved-ids/
    SKILL.md
    scripts/export_ids.js
    references/browser-collection.md
tests/
```

This keeps publishing documentation and tests outside the installed skill. Use `compatibility` for browser and artifact capabilities and repeat essential prerequisites in the body: some clients remove frontmatter when activating a skill. [Client activation guidance](https://agentskills.io/client-implementation/adding-skills-support#step-3-activation).

Keep vendor-only fields out of the shared frontmatter. Claude Code adds invocation controls, subagent execution, and dynamic shell interpolation; its documentation explicitly says that claude.ai uploads and API packaging reject unsupported frontmatter fields. Its standard-compatible fields work without those extensions. [Claude Code portability guidance](https://code.claude.com/docs/en/skills#using-skill-frontmatter-outside-claude-code).

## Portable plugin wrapper

Agent Plugins is a separate, published packaging standard. Version 1.0.0 requires root `plugin.json` with `$schema` and `name`. Skills belong in `skills/<name>/SKILL.md`; plugin clients discover immediate child skill directories, not arbitrarily nested categories. Optional MCP configuration belongs in root `mcp.json`. Client-specific data belongs under reverse-domain keys in `extensions`. A skill-only package needs no MCP server. [Agent Plugins specification](https://agent-plugins.org/specification).

The minimal wrapper is:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "indexx-instagram-skill"
}
```

Its official schema can validate manifest structure. Installation, permissions, and client-specific functionality remain outside the shared packaging contract. [Manifest schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json), [Agent Plugins overview](https://agent-plugins.org/).

The standard's client registry lists Cursor, VS Code, GitHub Copilot, ChatGPT & Codex, Kiro, Hermes Agent, OpenClaw, Grok Bot, and NanoClaw. That is documented package support, not proof that this Instagram browser workflow runs in each. [Compatible clients](https://agent-plugins.org/compatible-clients).

Recommendation: ship the root wrapper and preserve independent skill installation for clients that only understand Agent Skills. This avoids maintaining different copies of the workflow.

## Documented host support

OpenAI documents the same Agent Skills format for ChatGPT and Codex. Standalone skill support is available in the desktop app, Codex CLI, and IDE extension; plugin-bundled skills extend to Chat and Work on ChatGPT web, desktop, and mobile. Codex discovers local skills under repository and personal `.agents/skills/` directories. Invocation uses `@` in ChatGPT and `$` or `/skills` in Codex CLI/IDE. [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills).

Current OpenAI packaging guidance prefers root `plugin.json` with fixed `skills/` discovery. It accepts `.codex-plugin/plugin.json` as a compatibility fallback. When root `extensions.com.openai` is present, it replaces the fallback's OpenAI settings rather than merging with them. This repository uses the fallback to retain compatibility with older Codex tooling. Public directory distribution requires a separate review and publication; a GitHub release alone does not establish a ChatGPT listing. [OpenAI package specification](https://developers.openai.com/plugins/build/plugins), [public submission](https://developers.openai.com/plugins/deploy/submission).

All paths below are directories into which the entire `instagram-saved-ids/` folder goes.

| Host | Project/workspace location | Personal location | Relevant behavior |
| --- | --- | --- | --- |
| Cursor | `.agents/skills/` or `.cursor/skills/` | `~/.agents/skills/` or `~/.cursor/skills/` | Discovers skills automatically; `/` can invoke them. Only `~/.cursor/skills/` participates in its optional personal-skill cloud sync. [Cursor docs](https://cursor.com/docs/skills) |
| OpenClaw | `<workspace>/skills/` or `<workspace>/.agents/skills/` | `<state-dir>/skills/`, normally `~/.openclaw/skills/` | Also reads `~/.agents/skills/` for default-state agents. Custom state directories change that behavior. [OpenClaw docs](https://docs.openclaw.ai/tools/skills) |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | Supports standard skill folders, including symlinked folders; local personal skills do not automatically become cloud skills. [Claude Code docs](https://code.claude.com/docs/en/skills#choose-where-skills-load) |
| GitHub Copilot | `.github/skills/`, `.claude/skills/`, or `.agents/skills/` | `~/.copilot/skills/` or `~/.agents/skills/` | Documented across Copilot agent products; product/account enablement still applies. [GitHub docs](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) |
| Gemini CLI | `.gemini/skills/` or `.agents/skills/` | `~/.gemini/skills/` or `~/.agents/skills/` | Offers `/skills list` and `/skills reload`; native installer accepts repositories and local `.skill` packages. [Gemini CLI docs](https://geminicli.com/docs/cli/using-agent-skills/) |
| OpenCode | `.opencode/skills/`, `.claude/skills/`, or `.agents/skills/` | `~/.config/opencode/skills/`, `~/.claude/skills/`, or `~/.agents/skills/` | Loads through its `skill` tool; permission settings can hide or require approval for skills. [OpenCode docs](https://opencode.ai/docs/skills/) |

`.agents/skills/` is therefore a useful shared installation convention, but not a universal path. A repository containing `skills/instagram-saved-ids/` is a distribution source; clients may still need installation into their discovery directories.

## Distribution

Vercel's open `skills` CLI supports repository sources, named skills, multiple target agents, global installation, and copying instead of symlinking. It discovers both root skills and `skills/<name>/SKILL.md`. The following commands target this repository: [skills CLI documentation](https://github.com/vercel-labs/skills).

```sh
# Inspect what the repository contains.
npx skills add NYLLON-SOFTWARE/indexx-instagram-skill --list

# Install the selected skill for the current project.
npx skills add NYLLON-SOFTWARE/indexx-instagram-skill \
  --skill instagram-saved-ids \
  -a codex -a cursor -a claude-code -a openclaw --copy
```

Add `--global` for personal installation. `--copy` avoids relying on cross-directory symlink behavior. The installer provides distribution convenience, not certification that the workflow can run in every listed host.

OpenClaw's native Git/local installer expects `SKILL.md` at the source root. For a repository using the nested layout above, install the skill subdirectory locally, copy that directory, or use the `skills` CLI. Do not advertise a native whole-repository install without verifying its handling of this layout. Workspace symlinks outside configured roots may be rejected. ClawHub is an optional additional registry, not required for local skill use. [OpenClaw installation and containment rules](https://docs.openclaw.ai/tools/skills).

## Browser capability is the main practical limit

The intended user experience is selecting the skill from an agent browser-extension sidebar and running it against the authenticated Instagram tab. OpenAI documents side chat beside the current page and browser control through its extension. Skill selection remains an agent feature; this package does not create an independent Chrome extension. [Browser extension documentation](https://learn.chatgpt.com/docs/chrome-extension).

No Python or Node.js installation is required for that workflow. The bundled normalizer is pure JavaScript and returns export contents to the host's artifact/download tools. Developer-only validation, tests, and ZIP packaging also use JavaScript. Durable cross-session resume still depends on the host's checkpoint storage; temporary in-memory state alone cannot promise it.

This workflow must be able to open the user's authorized Saved grid, read item URLs, scroll the actual grid, preserve batches outside the page, and normalize batches using JavaScript in the agent/extension runtime. A model's ability to read the skill does not demonstrate those capabilities.

- Cursor has browser controls and workspace-isolated persistent sessions. That does not establish that the user's ordinary browser login is already available inside Cursor. Verify the actual browser profile and exposed link-extraction tools. [Cursor browser docs](https://cursor.com/docs/agent/tools/browser).
- OpenClaw distinguishes its isolated managed profile from attachment to a signed-in user Chrome session. Its login documentation recommends manual sign-in and explicit profile selection when existing sessions matter. [OpenClaw browser overview](https://docs.openclaw.ai/tools/browser), [browser login](https://docs.openclaw.ai/tools/browser-login).
- Other hosts need an available browser integration with equivalent capabilities. An MCP browser can supply tools where supported, but the skill should discover and follow that integration's actual API rather than assume tool names such as `cua_repl` exist everywhere.

Keep collection instructions expressed as capabilities. Place concrete browser examples in reference documentation and label them as examples for a particular runtime. Preserve the exporter's existing boundaries: read only the exposed grid, keep checkpoints outside the public skill package, distinguish partial collection from observed exhaustion, and never turn an installation success into a claim that all Saved items were exported.

## What remains to validate per host

Validation covers the JavaScript helper in an isolated runtime with no Node, DOM, or network APIs, export behavior from both release ZIPs, and a temporary-project `skills` CLI installation targeting Codex, Cursor, Claude Code, and OpenClaw. The CLI produced the expected shared `.agents/skills/`, Claude `.claude/skills/`, and OpenClaw `skills/` copies. These checks do not establish browser behavior inside the actual products.

Continuous validation uses a JavaScript check of the Agent Skills frontmatter constraints and relative resources, plus the published Agent Plugins 1.0.0 JSON Schema. The skill also passed the official `skills-ref` validator during initial research. The standard `compatibility` field is retained to document the host capabilities this workflow requires.

For each supported runtime, separately record: skill discovery, access to relative resources, execution of the normalizer on synthetic checkpoints, and a user-authorized browser run covering collection, interruption/resume, and completion evidence. Until those browser runs exist, describe that host as format-compatible with prerequisites, not end-to-end tested.
