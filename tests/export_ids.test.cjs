const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// The test harness uses Node; the skill runs with browser-standard globals only.
const context = vm.createContext({ URL });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../skills/instagram-saved-ids/scripts/export_ids.js'), 'utf8'), context);
const normalize = (batches, options = { reason: 'Synthetic test' }) =>
  JSON.parse(JSON.stringify(context.normalizeSavedItems(batches, options)));
const batch = (links, account = 'example') => ({
  source_url: `https://www.instagram.com/${account}/saved/all-posts/`,
  captured_at: '2026-09-09T12:00:00Z', links,
});

test('runs without Node, filesystem, browser DOM, or network APIs', () => {
  for (const key of ['require', 'process', 'document', 'fetch']) assert.equal(context[key], undefined);
  const data = fs.readFileSync(path.join(__dirname, '../examples/checkpoints.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  const { result, files } = normalize(data);
  assert.equal(result.unique_count, 3);
  assert.equal(result.coverage.status, 'partial');
  assert.equal(result.coverage.server_total_verified, false);
  assert.deepEqual(JSON.parse(files['saved-items.json']), result);
  assert.deepEqual(files['saved-ids.txt'].trim().split('\n'), result.items.map(item => item.id));
  assert.equal(files['saved-items.csv'].trim().split('\r\n').length, 4);
});

test('deduplicates URL aliases without folding shortcode case or dropping unbadged tiles', () => {
  const { result } = normalize([batch([
    { url: '/p/AbC/' }, { url: '/reel/AbC/', badges: ['Clip'] },
    { url: '/reels/AbC/' }, { url: '/p/abc/' }, { url: '/p/Slides/', badges: ['Carousel'] },
  ])]);
  assert.equal(result.unique_count, 3);
  assert.equal(result.items[0].type, 'reel');
  assert.equal(result.items[0].observed_urls.length, 3);
  assert.equal(result.items[1].type, 'post_or_reel');
  assert.equal(result.items[2].type, 'carousel');
});

test('retains conflicting observed media types', () => {
  const { result } = normalize([batch([
    { url: '/p/AbC/', badges: ['Carousel'] }, { url: '/reel/AbC/' },
  ])]);
  assert.equal(result.items[0].type, 'unknown');
  assert.deepEqual(result.items[0].observed_types, ['carousel', 'reel']);
});

test('keeps numeric identifiers as strings and separates identifier kinds', () => {
  const id = '12345678901234567890';
  const { result } = normalize([batch([{ url: `/stories/example/${id}/` }, { url: `/p/${id}/` }])]);
  assert.equal(result.unique_count, 2);
  assert.equal(result.items[0].id, id);
  assert.equal(result.items[0].id_kind, 'story_id');
  assert.equal(result.items[1].id_kind, 'shortcode');
});

test('retains unresolved links and rejects unrelated or credential-bearing origins', () => {
  const values = ['/unknown/ABC/', '/stories/highlights/123/',
    'https://example.com/p/ABC/', 'https://www.instagram.com.evil.example/p/ABC/',
    'https://user:password@www.instagram.com/p/ABC/'];
  const { result } = normalize([batch(values.map(url => ({ url })))]);
  assert.equal(result.unique_count, 0);
  assert.equal(result.unresolved_links.length, values.length);
});

test('rejects mixed accounts and malformed checkpoints', () => {
  assert.throws(() => normalize([batch([], 'one'), batch([], 'two')]), /Mixed-account/);
  assert.throws(() => normalize([{ ...batch([]), source_url: 'https://www.instagram.com/example/' }]), /source must/);
  assert.throws(() => normalize([{ ...batch([]), captured_at: '' }]), /captured_at/);
  assert.throws(() => normalize([{ ...batch([]), links: null }]), /links must/);
});

test('requires coverage evidence and prevents contradictory empty exports', () => {
  assert.throws(() => normalize([batch([])], {}), /reason/);
  assert.throws(() => normalize([batch([])], { status: 'complete', reason: 'Synthetic' }), /status/);
  for (const url of ['/p/ABC/', '/unknown/ABC/']) {
    assert.throws(() => normalize([batch([{ url }])], { status: 'empty', reason: 'Synthetic' }), /empty capture/);
  }
  const { result } = normalize([batch([])], { status: 'end-observed', reason: 'Synthetic checks' });
  assert.equal(result.coverage.status, 'end-observed');
  assert.equal(result.coverage.server_total_verified, false);
});
