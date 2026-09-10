const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { unzipSync } = require('fflate');
const ROOT = path.resolve(__dirname, '..');

test('archives are reproducible, self-contained, and exclude private data and development tools', async t => {
  const { buildRelease, SKILL_FILES } = await import('../scripts/build-release.mjs');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'instagram-skill-release-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const source = path.join(temp, 'source');
  fs.mkdirSync(source);
  for (const name of ['skills', '.codex-plugin', 'plugin.json', 'README.md', 'LICENSE']) {
    if (fs.existsSync(path.join(ROOT, name))) fs.cpSync(path.join(ROOT, name), path.join(source, name), { recursive: true });
  }
  fs.writeFileSync(path.join(source, 'skills/instagram-saved-ids/private-capture.jsonl'), 'PRIVATE_SENTINEL');
  fs.writeFileSync(path.join(source, 'skills/instagram-saved-ids/scripts/credentials.txt'), 'PRIVATE_SENTINEL');
  const archives = buildRelease(source, path.join(temp, 'dist'));
  const bytes = archives.map(file => fs.readFileSync(file));
  buildRelease(source, path.join(temp, 'dist'));
  assert.deepEqual(archives.map(file => fs.readFileSync(file)), bytes);
  const batches = fs.readFileSync(path.join(ROOT, 'examples/checkpoints.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  for (const archive of bytes) {
    const files = unzipSync(archive);
    for (const [name, contents] of Object.entries(files)) {
      assert(!Buffer.from(contents).includes('PRIVATE_SENTINEL'));
      assert(!name.endsWith('.jsonl') && !name.endsWith('.py') && !name.includes('node_modules/'));
      assert(!name.endsWith('package.json') && !name.endsWith('package-lock.json'));
    }
    const prefix = files['instagram-saved-ids/SKILL.md'] ? 'instagram-saved-ids/' : 'skills/instagram-saved-ids/';
    for (const relative of SKILL_FILES) assert(files[prefix + relative], relative);
    const context = vm.createContext({ URL });
    vm.runInContext(Buffer.from(files[prefix + 'scripts/export_ids.js']).toString(), context);
    const { result, files: exports } = context.normalizeSavedItems(batches, { reason: 'Synthetic packaged smoke test' });
    assert.equal(result.unique_count, 3);
    assert.equal(JSON.parse(exports['saved-items.json']).unique_count, 3);
  }
});

test('skill validation accepts standard metadata and catches broken packages', async t => {
  const { validateSkill } = await import('../scripts/validate.mjs');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'instagram-skill-validation-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const directory = path.join(temp, 'example-skill');
  fs.mkdirSync(directory);
  const write = (fields, body = 'Collect the requested records.') => fs.writeFileSync(path.join(directory, 'SKILL.md'), `---\n${fields}\n---\n${body}\n`);
  const base = 'name: example-skill\ndescription: Export records';
  write(base + '\ncompatibility: Browser tools\nmetadata:\n  version: "1"');
  assert.equal(validateSkill(directory).name, 'example-skill');
  for (const extra of ['\nunknown: true', '\nmetadata:\n  version: 1', `\ncompatibility: ${'x'.repeat(501)}`]) {
    write(base + extra);
    assert.throws(() => validateSkill(directory));
  }
  write(base, 'Read [the helper](scripts/missing.js).');
  assert.throws(() => validateSkill(directory));
  write('name: wrong-folder\ndescription: Export records');
  assert.throws(() => validateSkill(directory));
});
