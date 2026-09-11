# Host capabilities

Use this reference when selecting the browser tools, setting up a new host, or reporting a missing capability. Follow that host's live tool documentation and permissions; tool names below are illustrative categories, not callable APIs.

| Capability | Required behavior |
| --- | --- |
| Authenticated browser | Open or attach to a user-authorized session that can view the requested account's Saved grid. |
| Navigation and scrolling | Follow the All posts link, scroll the actual grid, and observe loading or challenges. |
| Exact URL capture | Read actual Saved-item URLs through DOM/link inspection, accessibility values, permitted read-only evaluation, or opening a saved tile and reading its full permalink through supported address-field or Copy link tools. Thumbnail screenshots alone are insufficient. |
| JavaScript data processing | Run the pure `scripts/export_ids.js` helper in the host's permitted agent runtime. It needs standard JavaScript and `URL`, with no imports or external packages. Browser control alone does not guarantee this facility. |
| Checkpoint and export tools | Save scoped batches and generated file contents through the host's supported private storage, download, or artifact mechanism. Persistent checkpoints enable resume across sessions. |

## Select an available route

Follow the user's chosen browser or tab. Otherwise prefer an already-authorized session with structured URL access. Check the live tools before requiring an installation: the extension is one route, not a prerequisite.

| Available route | How to collect |
| --- | --- |
| Browser extension or configured browser integration | Reuse the authorized tab and inspect Saved-grid link destinations through the documented browser API. |
| Built-in or managed browser | Open the Saved page with the host's browser tools. Its profile may differ from the user's regular browser; hand off sign-in if needed. Use its available DOM/link tools or the Computer Use procedure. |
| Computer Use without a browser extension | Operate the permitted browser app. Reuse its existing account session when available. Prefer accessibility/link values; otherwise open each saved tile and obtain its exact permalink. See the Computer Use section in [browser-collection.md](browser-collection.md). |

Native Computer Use provides visual app interaction; it does not guarantee DOM evaluation, JavaScript processing, clipboard reading, or file access. Test the required capabilities separately. If the chosen route cannot expose exact URLs, use another available route within the user's scope or report the missing capability. Do not substitute guessed IDs or quietly switch accounts.

## Host details

- **Browser extension/sidebar:** Select the installed skill in the sidebar and use the extension's authorized tab context, browser actions, JavaScript processing, and artifact tools. The agent runs the workflow; the user does not run a script or open a terminal.
- **ChatGPT or Codex outside the browser:** Use the built-in browser, configured browser integration, or installed and enabled Computer Use. In ChatGPT desktop, browser/computer tasks are documented for Work or Codex. Read the current tool instructions before selecting a tab or app. A new browser profile may require user sign-in. DOM or developer access remains governed by the host's permissions; an unavailable DOM is a reason to try the exact-URL UI route, not to assume elevated browser access.
- **Cursor or Claude Code:** Use a configured browser integration that supports the capability table. A terminal or web-search tool alone does not give access to private Saved items.
- **OpenClaw:** Use its documented browser tool with the intended profile. Have the user sign in in that profile if necessary; a managed browser may have different sessions from their everyday browser. Respect tool-policy restrictions on evaluation and file access.
- **Other Agent Skills hosts:** Map these capabilities to the tools actually exposed. Keep the same checkpoint and output contract.

Keep data processing outside the Instagram page. A `SKILL.md` or JavaScript file does not install itself as extension code: the agent reads the skill and executes the helper through its permitted tools. Do not inject a downloader, hidden API client, or storage shim into Instagram to compensate for missing host capabilities.

If a host lacks persistent storage, session state can retain batches during the current run, but cannot guarantee recovery after interruption. Deliver generated exports through available attachments/downloads or permitted writes to the user's output directory; inspect the returned attachment or file to verify delivery. If these are unavailable, offer copyable export contents when they fit. If JavaScript processing itself is unavailable, preserve any captured checkpoint and explain that normalized exports could not be generated. Do not claim files were saved or durable resume is available without those capabilities.

## Login and private data

The user handles sign-in and challenges through the host's supported handoff. Reuse authenticated access without requesting cookie exports, passwords, tokens, or private API credentials. Keep saved-item data in the user's output location and out of skill packages, repositories, and logs intended for sharing. Hosting this repository adds no collection server; the user's chosen agent and browser provider still handle data under their own settings.
