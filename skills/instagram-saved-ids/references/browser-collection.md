# Browser collection and checkpoints

Observed on 2026-09-09 (Pacific time): the All Posts page exposed grid links under `main article a[href]`; reel tiles used `/p/CODE/` URLs and an element with `aria-label="Clip"`. Scrolling loaded a second batch containing `Carousel` badges and unbadged tiles as well. All three shapes were captured by the same selector. Re-inspect the current DOM before reusing selectors. Badge names can vary with language; retain unknown types rather than guessing.

After confirming the current grid container, adapt this read-only DOM function to the host's documented evaluation tool. It is a function body to pass through that tool, not a required API name or a standalone browser script. If evaluation is unavailable, collect equivalent `url` and `badges` values through rendered DOM/link inspection. A screenshot alone does not expose exact shortcodes.

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

The source URL comes from the tab's documented URL accessor; attach `source_url` and a UTC ISO `captured_at` timestamp outside page evaluation. Retain each batch in the agent/extension runtime and checkpoint one JSON object per line through available artifact/storage tools. Scroll through supported browser or keyboard actions, then obtain a fresh state before deciding the next action. The sample scroll metrics apply to a document-scrolled grid; inspect and adapt if the grid has its own scrolling element. A progressbar being absent is only one signal, not a completeness guarantee.

The badge filter above only limits metadata; it does not filter the links. Preserve that distinction when adapting the extractor. Keep checkpoints and exports in the user's private artifact/storage location outside the installed skill. The JavaScript normalizer needs no credentials, network access, local Python, or Node.js installation.

Checkpoint shape (synthetic example):

```json
{"source_url":"https://www.instagram.com/example/saved/all-posts/","captured_at":"2026-09-09T12:00:00Z","links":[{"url":"/p/Example_Ab1/","badges":["Clip"]}],"loading":false,"scroll":{"top":0,"height":2000,"viewport":900}}
```

The helper normalizes `/p/`, `/reel/`, `/reels/CODE/`, and `/tv/` aliases to the same shortcode key. It also recognizes `/stories/USERNAME/NUMERIC_ID/` if actually captured inside the grid. Story viewer URLs without an item ID and highlight/collection URLs are rejected. Unknown item routes stay in `unresolved_links` for review; inspect actual grid items and extend parsing only after observing a new format.

Use a fresh checkpoint file per account and capture run. On resume, append to that run's file; the exporter rejects mixed-account sources. Never paste a whole page snapshot into the helper: it accepts only deliberately scoped `links` batches. It cannot determine whether a supplied link genuinely came from Saved.
