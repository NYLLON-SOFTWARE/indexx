# Browser collection and checkpoints

Observed on 2026-09-09 (Pacific time): the All Posts page exposed grid links under `main article a[href]`; reel tiles used `/p/CODE/` URLs and an element with `aria-label="Clip"`. Scrolling loaded a second batch containing `Carousel` badges and unbadged tiles as well. All three shapes were captured by the same selector. Re-inspect the current DOM before reusing selectors. Badge names can vary with language; retain unknown types rather than guessing.

## DOM or structured link access

After confirming the current grid container, adapt this read-only DOM function to the host's documented evaluation tool. It is a function body to pass through that tool, not a required API name or a standalone browser script. If evaluation is unavailable, collect equivalent `url` and `badges` values through rendered DOM/link inspection or use the Computer Use route below.

```javascript
() => ({
  links: Array.from(document.querySelectorAll('main article a[href]')).map(a => ({
    url: a.getAttribute('href'),
    badges: Array.from(a.querySelectorAll('[aria-label]'))
      .map(e => e.getAttribute('aria-label'))
      .filter(s => s === 'Clip' || s === 'Carousel')
  })),
  loading: !!document.querySelector('main article [role="progressbar"]'),
  scroll: {
    top: document.scrollingElement?.scrollTop ?? null,
    height: document.scrollingElement?.scrollHeight ?? null,
    viewport: document.scrollingElement?.clientHeight ?? null
  }
})
```

The source URL comes from the tab's documented URL accessor; attach `source_url` and a UTC ISO `captured_at` timestamp outside page evaluation. Retain each batch in the agent runtime and checkpoint one JSON object per line through available artifact/storage tools. Scroll through supported browser or keyboard actions, then obtain a fresh state before deciding the next action. The sample scroll metrics apply to a document-scrolled grid; inspect and adapt if the grid has its own scrolling element. A progressbar being absent is only one signal, not a completeness guarantee.

The badge filter above only limits metadata; it does not filter the links. Preserve that distinction when adapting the extractor. Keep checkpoints and exports in the user's private artifact/storage location outside the installed skill. The JavaScript normalizer needs no credentials, network access, local Python, or Node.js installation.

## Computer Use without DOM access

Use this route when an enabled Computer Use tool can operate the browser but cannot enumerate grid links. It is slower because each tile may need to be opened. Do not impose an arbitrary item limit; continue under the user's requested scope and checkpoint partial progress if access or tool limits interrupt the run.

1. Confirm the account and Saved **All Posts** page from the browser UI. Record that full Saved URL as `source_url`, and identify the visible grid rows before opening anything.
2. Work through every visible saved tile in a consistent order. Prefer a readable link destination from the host's accessibility surface or supported link-copy action. Otherwise open the tile and read its full permalink from the address field or the post's **Copy link** action, using the host's supported text/clipboard facility. Read only the post link just copied. If a modal leaves the Saved URL in the address bar, that URL is not the item's permalink.
3. Keep the grid position when opening a separate tab or closing a post view. On return, take a fresh observation before selecting the next tile; coordinates from a prior layout can point at a different item. If the position is lost, resume from the top and deduplicate. Keep `source_url` as the original Saved page while each captured `url` identifies the post opened from that grid. Do not add recommended or neighboring viewer items without establishing their origin in Saved.
4. Preserve URL case. Record only media badges actually observed; use `badges: []` when none are available. If no tool exposes an exact complete permalink, record the tile as unresolved in the checkpoint rather than inferring an ID from a thumbnail, caption, or truncated address. An unresolved record can use `url: null` with a brief `reason`; the normalizer retains it in `unresolved_links`.
5. Checkpoint the current viewport's links before scrolling with overlap. Record absent numeric scroll metrics as `null`, not invented values. Keep brief `observation` text describing the visible tail, loading, and whether scroll actions moved the grid. Use the main skill's settled end checks; if visual evidence cannot establish exhaustion, deliver `partial`.

These steps define a fallback to validate in the actual host; the historical DOM observation above does not establish a completed Computer Use run. All routes feed the same batches into the same JavaScript normalizer and host delivery tools.

## Shared checkpoints

Checkpoint shape (synthetic example):

```json
{"source_url":"https://www.instagram.com/example/saved/all-posts/","captured_at":"2026-09-09T12:00:00Z","links":[{"url":"/p/Example_Ab1/","badges":["Clip"]}],"loading":false,"scroll":{"top":0,"height":2000,"viewport":900}}
```

The helper normalizes `/p/`, `/reel/`, `/reels/CODE/`, and `/tv/` aliases to the same shortcode key. It also recognizes `/stories/USERNAME/NUMERIC_ID/` if actually captured inside the grid. Story viewer URLs without an item ID and highlight/collection URLs are rejected. Unknown item routes stay in `unresolved_links` for review; inspect actual grid items and extend parsing only after observing a new format.

Use a fresh checkpoint file per account and capture run. On resume, append to that run's file; the exporter rejects mixed-account sources. Never paste a whole page snapshot into the helper: it accepts only deliberately scoped `links` batches. It cannot determine whether a supplied link genuinely came from Saved.
