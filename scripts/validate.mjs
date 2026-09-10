import assert from 'node:assert/strict';
import { readFileSync, readdirSync, realpathSync, statSync } from 'node:fs';
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import { lexer, walkTokens } from 'marked';
import { parse } from 'yaml';
import { ROOT } from './build-release.mjs';

const PLUGIN_SCHEMA = 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json';

// Frontmatter constraints from https://agentskills.io/specification.
export function validateSkill(directory) {
  const source = readFileSync(join(directory, 'SKILL.md'), 'utf8');
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]+)$/.exec(source);
  assert(match, 'SKILL.md needs YAML frontmatter and a Markdown body');
  const fields = parse(match[1]);
  assert(fields && typeof fields === 'object' && !Array.isArray(fields), 'Frontmatter must be a mapping');
  const allowed = new Set(['name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools']);
  for (const key of Object.keys(fields)) assert(allowed.has(key), `Unsupported skill field: ${key}`);
  assert.equal(typeof fields.name, 'string', 'Skill name must be a string');
  assert(/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(fields.name) && fields.name.length <= 64, 'Invalid skill name');
  assert.equal(fields.name, basename(directory), 'Skill name must match its folder');
  const checkString = (key, maximum) => {
    assert(typeof fields[key] === 'string' && fields[key].trim().length > 0 && fields[key].length <= maximum, `Invalid ${key}`);
  };
  checkString('description', 1024);
  if ('compatibility' in fields) checkString('compatibility', 500);
  for (const key of ['license', 'allowed-tools']) if (key in fields) checkString(key, Infinity);
  if ('metadata' in fields) {
    assert(fields.metadata && typeof fields.metadata === 'object' && !Array.isArray(fields.metadata), 'Metadata must be a mapping');
    assert(Object.values(fields.metadata).every(value => typeof value === 'string'), 'Metadata values must be strings');
  }
  assert(match[2].trim(), 'Skill instructions must not be empty');
  const root = realpathSync(directory);
  walkTokens(lexer(match[2]), token => {
    if (token.type !== 'link' && token.type !== 'image') return;
    const target = token.href;
    if (!target || /^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith('#')) return;
    const resource = realpathSync(resolve(root, target.split('#')[0]));
    const inside = relative(root, resource);
    assert(inside && !isAbsolute(inside) && inside !== '..' && !inside.startsWith(`..${sep}`), `External skill resource: ${target}`);
    assert(statSync(resource).isFile(), `Missing skill resource: ${target}`);
  });
  return fields;
}

export async function validate(root = ROOT) {
  for (const entry of readdirSync(join(root, 'skills'), { withFileTypes: true })) {
    if (entry.isDirectory()) validateSkill(join(root, 'skills', entry.name));
  }
  const manifest = JSON.parse(readFileSync(join(root, 'plugin.json'), 'utf8'));
  assert.equal(manifest.$schema, PLUGIN_SCHEMA, 'Use the Agent Plugins 1.0.0 schema');
  const response = await fetch(PLUGIN_SCHEMA, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`Schema request failed: HTTP ${response.status}`);
  const check = new Ajv2020({ allErrors: true }).compile(await response.json());
  assert(check(manifest), JSON.stringify(check.errors));
  console.log('Agent Skills frontmatter/resources and Agent Plugins schema are valid');
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) await validate();
