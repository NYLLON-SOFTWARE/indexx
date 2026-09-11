# ChatGPT plugin compatibility and distribution

Researched 2026-09-10 against fetched official OpenAI documentation. This note addresses the runtime choice for the existing browser-sidebar skill; it does not establish a successful live Instagram export or directory approval.

## Recommendation

Keep the Instagram capture workflow as a **skills-only plugin using available browser or Computer Use tools**. Prefer structured URL access in an authorized session; a browser extension is optional. A hosted MCP server and custom UI are optional additions for a future INDEXX service; they are unnecessary for packaging this workflow. OpenAI explicitly documents skills-only plugins and makes MCP optional. [MCP server concepts](https://developers.openai.com/plugins/concepts/mcp-server)

Current Apps SDK quickstart, UI, authentication, and submission URLs redirect into OpenAI's current `/plugins/` documentation. Describing today's integration as “plugins are discontinued; build an app instead” would misrepresent these sources. [MCP and UI quickstart](https://developers.openai.com/plugins/build/app-quickstart), [plugin submissions](https://developers.openai.com/plugins/deploy/submission)

## What this repository already provides

Inspected on local `main` at commit `4e2f2fa42f4614d3b9f60177b7f45938459a5bb1`:

| Component | Current state |
| --- | --- |
| Portable package | Root `plugin.json` declares Agent Plugins 1.0.0, a stable name, version, publisher, and repository. |
| Shared skill | `skills/instagram-saved-ids/SKILL.md` includes its JavaScript helper and references. |
| OpenAI presentation | `.codex-plugin/plugin.json` supplies display text, category, and a starter prompt. |
| Release packaging | The builder produces separate skill and plugin ZIPs using explicit file allowlists. |
| Public listing materials | The current manifest has no logo, support URL, privacy-policy URL, or terms URL. |
| Execution evidence | Automated validation exists; a fresh plugin installation and complete live sidebar export remain unverified. |

This is already a plugin-shaped repository, not a standalone skill needing a new backend. OpenAI prefers root `plugin.json` and fixed `skills/` discovery. Its current documentation still supports the existing `.codex-plugin/plugin.json` fallback. [Package your plugin](https://developers.openai.com/plugins/build/plugins)

An optional modernization is moving the complete OpenAI presentation object into `plugin.json` under `extensions.com.openai.interface`. That inline extension replaces the fallback settings rather than merging with them. Keep the standalone skill directory for other Agent Skills hosts. If branding assets are added, extend the release allowlist so referenced assets actually ship. [Package your plugin](https://developers.openai.com/plugins/build/plugins)

## The browser runtime is separate from packaging

**Documented:** OpenAI's browser extension lets the desktop agent read and act in sites where the user is already signed in. Chrome, Edge, Brave, and Vivaldi support side chat; Opera supports desktop browser control without side chat. The setup and browser-task instructions specifically say to start a **ChatGPT Work or Codex chat** and mention the connected browser or tab. Availability can depend on rollout and workspace settings. [Browser extension](https://learn.chatgpt.com/docs/chrome-extension)

**Documented:** The built-in browser is available on ChatGPT web and desktop, but its profile is separate from the regular browser; existing tabs and sessions are not automatically shared. The docs direct users to the extension when they need an existing regular-browser tab/session. Desktop browser computer use is described for Work or Codex. [Browser](https://learn.chatgpt.com/docs/browser)

**Implication:** Plugin installation does not by itself establish access to the user's Instagram session. Select an available extension, built-in browser, browser integration, or native Computer Use route; verify account access, exact URLs, processing, and file delivery separately. Selecting the plugin in an ordinary web or mobile chat does not immediately grant access to an already-open Chrome tab.

**Documented:** Computer Use can operate desktop app interfaces in supported ChatGPT Work/Codex environments once installed and permitted. **Our fallback design:** when that includes the user's browser but no DOM inspection, open each Saved tile and read its full permalink through supported address-field, accessibility, or Copy link text tools. Preserve grid position, checkpoint batches, and reuse the same normalizer. A thumbnail or truncated URL cannot provide a trustworthy shortcode; report missing exact-URL access when no route supplies it. This is slower and remains untested on a full Instagram grid. [Computer Use](https://learn.chatgpt.com/docs/computer-use)

## What an MCP app/UI would change

**Documented:** Optional plugin UI components run inside a ChatGPT iframe and communicate with the host through the MCP Apps bridge, using JSON-RPC over `postMessage`. The standard is preferred for portable UI; `window.openai` provides optional ChatGPT extensions. Tools should remain useful without their UI. [Add UI to your MCP server](https://developers.openai.com/plugins/build/chatgpt-ui)

**Documented:** Widgets have an isolated iframe and strict Content Security Policy, with restricted browser APIs and nested frames blocked by default. [Security and privacy](https://developers.openai.com/plugins/guides/security-privacy)

**Architecture inference:** Moving `export_ids.js` into such a widget would provide a place to render or transform supplied data. It would not give that widget a browser-extension content script, tab-control permissions, or the user's Instagram session. The documented MCP Apps bridge is not a general remote-control interface to the user's other tabs. An MCP endpoint similarly needs its own authorized data source; OAuth to INDEXX would authorize INDEXX data, not automatically grant Instagram browser access.

## When hosted MCP would make sense

For a later product that searches already-imported INDEXX saved items, manages collections, or synchronizes results across devices, a remote MCP service could expose those operations. This is an architecture recommendation, not an implemented capability. Keep collection in the authorized browser, then send only explicitly authorized data to INDEXX.

Production remote MCP uses a stable HTTPS endpoint and Streamable HTTP; OpenAI documents both TypeScript and Python SDKs. An authenticated server uses MCP-compatible OAuth 2.1, with server-side token and scope validation. Choosing TypeScript would preserve JavaScript development, and hosting would keep installation/runtime setup off the user's machine. None of these server requirements apply merely because the current skill is packaged as a plugin. [MCP server concepts](https://developers.openai.com/plugins/concepts/mcp-server), [authentication](https://developers.openai.com/plugins/build/auth)

## Distribution consequences

The current submission portal accepts skills-only, remote MCP-only, and combined plugins. A skills-only submission does not require deploying an MCP server. Remote MCP submissions use a stable public HTTPS endpoint; local MCP publication support requires contacting OpenAI. Both paths involve listing/review materials, including verified publisher identity, public support/privacy/terms URLs, starter prompts, and five positive plus three negative test cases. A GitHub repository alone is not directory publication. [Submit plugins](https://developers.openai.com/plugins/deploy/submission)

Before public claims, verify a fresh plugin install can select the skill, use an authorized Instagram tab, scroll the Saved grid, create resumable checkpoints, deliver all three exports, and accurately report login challenges, partial results, and observed completion. Those are project-specific acceptance checks, distinct from package schema validation.

## Recommended next implementation

1. Keep the current skill and JavaScript normalizer. Finish install-surface metadata and brand assets; describe the required browser/computer and export capabilities explicitly. Do not invent a manifest permission that automatically grants Instagram access.
2. Add this existing package to a personal local marketplace, install it, and start a fresh conversation. Verify direct requests, paraphrased requests, follow-ups, and unsupported requests. This is the documented test route for a skills-only plugin. [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)
3. Exercise the actual browser workflow. Proposed acceptance cases: a small mixed-media Saved grid, duplicate URL aliases, interrupted collection/resume, an explicit empty grid, and complete JSON/CSV/text delivery. Negative cases: a different user's private Saved page, a login/challenge interruption, and unavailable browser or export tools. These are proposed cases, not recorded successes.
4. After those checks, use the public submission portal's **Create plugin → Skills only** route with the tested bundle and listing materials. Approval and the developer's publish action are separate steps. [Submit plugins](https://developers.openai.com/plugins/deploy/submission)

The first milestone should be a demonstrated installed plugin exporting through each claimed browser route, including a no-extension session. Directory publication comes afterward. Add MCP only if a later product requirement needs access to an INDEXX service or synchronized library.

The subsequent no-extension update changes skill routing and package descriptions. It does not establish a live browser test, install the plugin, create a marketplace, submit a listing, or publish a new release.
