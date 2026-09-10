/* Pure JavaScript for the extension/agent runtime. No imports, filesystem, or network access. */
function normalizeSavedItems(batches, { status = "partial", reason } = {}) {
  if (!["partial", "end-observed", "empty"].includes(status)) {
    throw new Error("Invalid coverage status");
  }
  if (typeof reason !== "string" || !reason.trim()) {
    throw new Error("A coverage reason is required");
  }
  if (!Array.isArray(batches) || !batches.length) {
    throw new Error("No checkpoint batches supplied");
  }
  const hosts = new Set(["instagram.com", "www.instagram.com"]);
  const items = new Map(), unresolved = [], times = [], accounts = new Set(), sources = new Set();
  const unique = values => [...new Set(values)].sort();
  const validURL = url => url.protocol === "https:" && hosts.has(url.host.toLowerCase())
    && !url.username && !url.password;
  const parseItem = (raw, base) => {
    if (!raw || typeof raw.url !== "string") return null;
    let url;
    try { url = new URL(raw.url, base); } catch { return null; }
    if (!validURL(url)) return null;
    const badges = Array.isArray(raw.badges) ? unique(raw.badges.filter(b => typeof b === "string")) : [];
    const media = /^\/(p|reel|reels|tv)\/([A-Za-z0-9_-]+)\/?$/.exec(url.pathname);
    if (media) {
      const [, route, code] = media;
      const type = ["reel", "reels"].includes(route) || badges.includes("Clip") ? "reel"
        : badges.includes("Carousel") ? "carousel" : route === "tv" ? "video" : "post_or_reel";
      return { id: code, id_kind: "shortcode", media_id: null, type,
        url: `https://www.instagram.com/${route}/${code}/`, badges };
    }
    const story = /^\/stories\/([A-Za-z0-9._]+)\/(\d+)\/?$/.exec(url.pathname);
    if (story && story[1].toLowerCase() !== "highlights") {
      return { id: story[2], id_kind: "story_id", media_id: null, type: "story",
        url: `https://www.instagram.com/stories/${story[1]}/${story[2]}/`, badges };
    }
    return null;
  };

  for (const [index, batch] of batches.entries()) {
    let source;
    try { source = new URL(batch.source_url); } catch { throw new Error(`Batch ${index + 1}: invalid source URL`); }
    const account = /^\/([A-Za-z0-9._]+)\/saved\/all-posts\/?$/.exec(source.pathname);
    if (!validURL(source) || !account) {
      throw new Error(`Batch ${index + 1}: source must be an Instagram /USERNAME/saved/all-posts/ URL`);
    }
    accounts.add(account[1].toLowerCase());
    sources.add(`https://www.instagram.com/${account[1]}/saved/all-posts/`);
    if (accounts.size > 1) throw new Error("Mixed-account checkpoints are not supported");
    if (typeof batch.captured_at !== "string" || !batch.captured_at) {
      throw new Error(`Batch ${index + 1}: captured_at is required`);
    }
    if (!Array.isArray(batch.links)) throw new Error(`Batch ${index + 1}: links must be a list`);
    times.push(batch.captured_at);
    for (const raw of batch.links) {
      const item = parseItem(raw, source.href);
      if (!item) { unresolved.push({ batch: index + 1, link: raw }); continue; }
      const key = `${item.id_kind}:${item.id}`;
      if (!items.has(key)) {
        items.set(key, { ...item, observed_urls: [item.url], observed_types: [item.type] });
      } else {
        const old = items.get(key);
        old.observed_urls = unique([...old.observed_urls, item.url]);
        old.badges = unique([...old.badges, ...item.badges]);
        old.observed_types = unique([...old.observed_types, item.type]);
        const known = old.observed_types.filter(type => type !== "post_or_reel");
        old.type = known.length === 1 ? known[0] : known.length ? "unknown" : "post_or_reel";
      }
    }
  }
  if (status === "empty" && (items.size || unresolved.length)) {
    throw new Error("An empty capture cannot contain items or unresolved links");
  }
  const result = {
    source_urls: [...sources].sort(), captured_from: times[0], captured_to: times[times.length - 1],
    coverage: { status, reason, server_total_verified: false }, batch_count: times.length,
    unique_count: items.size, unresolved_links: unresolved, items: [...items.values()],
  };
  const fields = ["id", "id_kind", "media_id", "type", "url"];
  const csvCell = value => {
    const text = value == null ? "" : String(value);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return {
    result,
    files: {
      "saved-items.json": JSON.stringify(result, null, 2) + "\n",
      "saved-items.csv": [fields.join(","), ...result.items.map(item => fields.map(field => csvCell(item[field])).join(","))].join("\r\n") + "\r\n",
      "saved-ids.txt": result.items.map(item => item.id + "\n").join(""),
    },
  };
}
