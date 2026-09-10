import { existsSync, mkdirSync, readFileSync, realpathSync, statSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { zipSync } from 'fflate';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const SKILL_NAME = 'instagram-saved-ids';
export const SKILL_FILES = [
  'SKILL.md', 'agents/openai.yaml', 'references/browser-collection.md',
  'references/runtime.md', 'scripts/export_ids.js',
];

export function buildRelease(root = ROOT, output = join(root, 'dist')) {
  root = realpathSync(root);
  const manifest = JSON.parse(readFileSync(join(root, 'plugin.json'), 'utf8'));
  const legacy = JSON.parse(readFileSync(join(root, '.codex-plugin/plugin.json'), 'utf8'));
  const { name, version } = manifest;
  if (typeof name !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) throw new Error('Invalid package name');
  if (typeof version !== 'string' || !/^\d+\.\d+\.\d+$/.test(version)) throw new Error('Release version must use major.minor.patch');
  for (const field of ['name', 'version', 'description', 'license', 'repository']) {
    if (legacy[field] !== manifest[field]) throw new Error(`Compatibility manifest differs on ${field}`);
  }
  const skillEntries = SKILL_FILES.map(path => [`skills/${SKILL_NAME}/${path}`, `${SKILL_NAME}/${path}`]);
  const pluginEntries = ['plugin.json', '.codex-plugin/plugin.json', 'README.md'].map(path => [path, path]);
  pluginEntries.push(...SKILL_FILES.map(path => [`skills/${SKILL_NAME}/${path}`, `skills/${SKILL_NAME}/${path}`]));
  if (existsSync(join(root, 'LICENSE'))) {
    skillEntries.push(['LICENSE', `${SKILL_NAME}/LICENSE`]);
    pluginEntries.push(['LICENSE', 'LICENSE']);
  } else if (manifest.license) {
    throw new Error('Manifest declares a license but LICENSE is missing');
  }

  // Read only allowlisted regular files, and check all inputs before writing outputs.
  const inputs = new Map();
  for (const [source] of [...skillEntries, ...pluginEntries]) {
    const path = realpathSync(join(root, source));
    const inside = relative(root, path);
    if (!inside || isAbsolute(inside) || inside === '..' || inside.startsWith(`..${sep}`) || !statSync(path).isFile()) {
      throw new Error(`Missing or external package input: ${source}`);
    }
    inputs.set(source, readFileSync(path));
  }
  const archives = [
    [join(output, `${SKILL_NAME}-${version}.zip`), skillEntries],
    [join(output, `${name}-${version}.zip`), pluginEntries],
  ];
  mkdirSync(output, { recursive: true });
  for (const [destination, entries] of archives) {
    const files = Object.fromEntries(entries.map(([source, path]) => [path, inputs.get(source)]));
    writeFileSync(destination, zipSync(files, {
      level: 6, mtime: new Date(2020, 0, 1), os: 3, attrs: 0o100644 << 16,
    }));
  }
  return archives.map(([path]) => path);
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const { values } = parseArgs({ options: { 'out-dir': { type: 'string', default: join(ROOT, 'dist') } } });
  for (const path of buildRelease(ROOT, resolve(values['out-dir']))) console.log(path);
}
