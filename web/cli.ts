#!/usr/bin/env bun
/**
 * hajimihomo CLI — generate a complete mihomo profile from preset + user config.
 *
 * Usage: hajimihomo [options]
 *   --preset   mini|lite|standard|full    (default: standard)
 *   --user     path/to/user.yaml          (default: profiles/user.yaml)
 *   --output   path/to/output/dir         (default: profiles/output)
 *   --catalog  path/to/rulesets.json      (default: dist/mihomo/rulesets.json)
 *   --format   yaml-split|yaml-classical|binary  (default: yaml-split)
 *   --geodata  metacubex|dustinwin        (default: metacubex)
 *   --target   mihomo|mihomo-smart        (overrides preset)
 *   --topology global|regional|advanced   (overrides preset)
 *   --help                                show this message
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'
import { buildFullProfile } from './src/ProfileBuilder.js'
import { buildHostsBlock } from './hosts.js'

const PRESET_DIR = 'profiles/presets'
const DEFAULT_USER = 'profiles/user.yaml'
const DEFAULT_OUTPUT = 'profiles/output'
const DEFAULT_CATALOG = 'dist/rulesets.json'

// ── arg parsing ──────────────────────────────────────────────────────────────

function parseArgs(argv: string[]): Record<string, string> {
  const args: Record<string, string> = {
    preset: 'standard',
    user: DEFAULT_USER,
    output: DEFAULT_OUTPUT,
    catalog: DEFAULT_CATALOG,
    format: 'yaml-split',
    geodata: 'metacubex',
  }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--help' || a === '-h') { printHelp(); process.exit(0) }
    const key = a.replace(/^--/, '')
    if (a.startsWith('--') && argv[i + 1] && !argv[i + 1].startsWith('--')) {
      args[key] = argv[++i]
    }
  }
  return args
}

function printHelp() {
  console.log(`\
hajimihomo — mihomo profile builder

Usage: hajimihomo [options]

Options:
  --preset    mini|lite|standard|full      (default: standard)
  --user      path/to/user.yaml            (default: profiles/user.yaml)
  --output    output directory             (default: profiles/output)
  --catalog   path/to/rulesets.json        (default: dist/mihomo/rulesets.json)
  --format    yaml-split|yaml-classical|binary  (default: yaml-split)
  --geodata   metacubex|dustinwin          (default: metacubex)
  --target    mihomo|mihomo-smart          (overrides preset)
  --topology  global|regional|advanced     (overrides preset)
  --help      show this message`)
}

// ── preset loading ───────────────────────────────────────────────────────────

function loadPreset(name: string): Record<string, any> {
  const files = [
    join(PRESET_DIR, `${name}.yaml`),
    // handle numbered prefix filenames like 3-standard.yaml
    ...['1', '2', '3', '4'].map(n => join(PRESET_DIR, `${n}-${name}.yaml`)),
  ]
  for (const f of files) {
    if (existsSync(f)) {
      const raw = readFileSync(f, 'utf8')
      return yaml.load(raw) as Record<string, any>
    }
  }
  throw new Error(`Preset '${name}' not found in ${PRESET_DIR}/`)
}

// ── user config loading ───────────────────────────────────────────────────────

interface UserConfig {
  proxy_providers?: Array<{ name: string; url: string; prefix?: string }>
  target?: string
  topology?: string
  geodata?: string
  format?: string
  extra_groups?: string[]
  skip_groups?: string[]
  region_excludes?: string
  hosts_enabled?: boolean
  hosts_include?: string[]
  hosts_exclude?: string[]
}

function loadUser(path: string): UserConfig {
  if (!existsSync(path)) {
    console.warn(`[warn] user config not found at ${path}, using defaults`)
    return {}
  }
  return (yaml.load(readFileSync(path, 'utf8')) || {}) as UserConfig
}

// ── main ─────────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs(process.argv.slice(2))

  // load preset + user config
  const preset = loadPreset(args.preset)
  const user   = loadUser(args.user)

  // merge: user overrides preset where specified
  const target   = args.target   || user.target   || preset.target   || 'mihomo'
  const topology = args.topology || user.topology  || preset.topology || 'regional'
  const geodata  = args.geodata  || user.geodata   || 'metacubex'
  const format   = args.format   || user.format    || 'yaml-split'

  // group IDs: start from preset, apply user add/remove
  let groupIds: string[] = preset.groups || []
  if (user.extra_groups?.length) groupIds = [...groupIds, ...user.extra_groups]
  if (user.skip_groups?.length) {
    const skip = new Set(user.skip_groups)
    groupIds = groupIds.filter((g: string) => !skip.has(g))
  }

  // subscription URLs from user config
  const subUrls: string[] = (user.proxy_providers || []).map((p: any) => p.url).filter(Boolean)

  // load rulesets catalog
  if (!existsSync(args.catalog)) {
    console.error(`[error] catalog not found at ${args.catalog}`)
    console.error(`  Run 'make build-groups' first to generate dist/rulesets.json`)
    process.exit(1)
  }
  const catalog = JSON.parse(readFileSync(args.catalog, 'utf8'))

  // build profile
  const opts: Record<string, any> = {
    topology,
    target,
    features: preset.features || {},
    regionExcludes: user.region_excludes || '',
    geodata,
    format,
  }

  let profile = buildFullProfile(subUrls, groupIds, catalog, opts)

  // optionally append hosts block
  if (user.hosts_enabled) {
    try {
      const hostsBlock = await buildHostsBlock({
        include: user.hosts_include || [],
        exclude: user.hosts_exclude || [],
      })
      if (hostsBlock) profile += '\n\n' + hostsBlock
    } catch (e) {
      console.warn(`[warn] hosts block build failed: ${(e as Error).message}`)
    }
  }

  // write output
  mkdirSync(args.output, { recursive: true })
  const outFile = join(args.output, `${args.preset}.yaml`)
  writeFileSync(outFile, profile + '\n')
  console.log(`[ok] wrote ${outFile}  (${(profile.length / 1024).toFixed(1)} KB)`)
}

main().catch(e => { console.error(e.message); process.exit(1) })
