# Host capabilities

Use this reference when selecting the browser tools, setting up a new host, or reporting a missing capability. Follow that host's live tool documentation and permissions; tool names below are illustrative categories, not callable APIs.

| Capability | Required behavior |
| --- | --- |
| Authenticated browser | Open or attach to a user-authorized session that can view the requested account's Saved grid. |
| Navigation and scrolling | Follow the All posts link, scroll the actual grid, and observe loading or challenges. |
| Rendered link inspection | Read actual tile URLs through DOM inspection, an accessibility surface exposing URLs, or permitted read-only page evaluation. Screenshots alone are insufficient. |
| JavaScript data processing | Run the pure `scripts/export_ids.js` helper in the host's permitted agent/extension runtime. It needs standard JavaScript and `URL`, with no imports or external packages. |
| Checkpoint and export tools | Save scoped batches and generated file contents through the host's supported private storage, download, or artifact mechanism. Persistent checkpoints enable resume across sessions. |

## Adapt to the host

- **Browser extension/sidebar:** Select the installed skill in the sidebar and use the extension's authorized tab context, browser actions, JavaScript processing, and artifact tools. The agent runs the workflow; the user does not run a script or open a terminal.
- **ChatGPT or Codex outside the browser:** Use the browser connection available in the task. Read the current browser tool instructions before selecting a tab or evaluating the page.
- **Cursor or Claude Code:** Use a configured browser integration that supports the capability table. A terminal or web-search tool alone does not give access to private Saved items.
- **OpenClaw:** Use its documented browser tool with the intended profile. Have the user sign in in that profile if necessary; a managed browser may have different sessions from their everyday browser. Respect tool-policy restrictions on evaluation and file access.
- **Other Agent Skills hosts:** Map these capabilities to the tools actually exposed. Keep the same checkpoint and output contract.

Keep data processing outside the Instagram page. A `SKILL.md` or JavaScript file does not install itself as extension code: the agent reads the skill and executes the helper through its permitted tools. Do not inject a downloader, hidden API client, or storage shim into Instagram to compensate for missing host capabilities.

If a host lacks persistent storage, session state can retain batches during the current run, but cannot guarantee recovery after interruption. If download/artifact creation is unavailable, offer copyable export contents when they fit; otherwise preserve available checkpoints and report the delivery limitation. Do not claim files were saved or durable resume is available without those capabilities.

## Login and private data

The user handles sign-in and challenges through the host's supported handoff. Reuse authenticated access without requesting cookie exports, passwords, tokens, or private API credentials. Keep saved-item data in the user's output location and out of skill packages, repositories, and logs intended for sharing. Hosting this repository adds no collection server; the user's chosen agent and browser provider still handle data under their own settings.
