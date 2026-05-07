#!/usr/bin/env bun
/**
 * hajimihomo CLI — generate a complete mihomo profile from preset + user config.
 *
 * Usage: hajimihomo [options]
 *   --preset   mini|lite|standard|full         (default: standard)
 *   --sub      https://airport.com/sub?tok=xxx  (repeatable; overrides user.yaml subs)
 *   --user     path/to/user.yaml               (default: profiles/user.yaml)
 *   --output   path/to/output/dir              (default: dist/profiles)
 *   --catalog  path/to/rulesets.json           (default: dist/rulesets.json)
 *   --format   yaml-split|yaml-classical|binary (default: yaml-split)
 *   --geodata  metacubex|dustinwin             (default: metacubex)
 *   --target   mihomo|mihomo-smart             (overrides preset)
 *   --topology global|regional|advanced        (overrides preset)
 *   --help                                     show this message
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { resolve, join, dirname } from 'node:path'
import { createInterface } from 'node:readline/promises'
import yaml from 'js-yaml'
import { buildFullProfile } from './src/ProfileBuilder.js'
import { buildHostsBlock } from './hosts.js'

const PRESET_DIR = 'profiles/presets'
const DEFAULT_USER = 'profiles/user.yaml'
const DEFAULT_OUTPUT = 'dist/profiles'
const DEFAULT_CATALOG = 'dist/rulesets.json'

// ── arg parsing ──────────────────────────────────────────────────────────────

interface ParsedArgs {
  flags: Record<string, string>
  subs: string[]   // --sub (repeatable)
}

function parseArgs(argv: string[]): ParsedArgs {
  const flags: Record<string, string> = {
    preset: 'standard',
    user: DEFAULT_USER,
    output: DEFAULT_OUTPUT,
    catalog: DEFAULT_CATALOG,
    format: 'yaml-split',
    geodata: 'metacubex',
  }
  const subs: string[] = []
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--help' || a === '-h') { printHelp(); process.exit(0) }
    if (a === '--sub' && argv[i + 1]) { subs.push(argv[++i]); continue }
    const key = a.replace(/^--/, '')
    if (a.startsWith('--') && argv[i + 1] && !argv[i + 1].startsWith('--')) {
      flags[key] = argv[++i]
    }
  }
  return { flags, subs }
}

function printHelp() {
  console.log(`\
hajimihomo — mihomo profile builder

Usage: hajimihomo [options]

Options:
  --preset    mini|lite|standard|full            (default: standard)
  --sub       subscription URL                   (repeatable; overrides user.yaml subs)
  --user      path/to/user.yaml                  (default: profiles/user.yaml)
  --output    output directory                   (default: dist/profiles)
  --catalog   path/to/rulesets.json              (default: dist/rulesets.json)
  --format    yaml-split|yaml-classical|binary   (default: yaml-split)
  --geodata   metacubex|dustinwin                (default: metacubex)
  --target    mihomo|mihomo-smart                (overrides preset)
  --topology  global|regional|advanced           (overrides preset)
  --help      show this message

When no --sub flags and no user.yaml exist, an interactive wizard runs to
collect subscription URLs and optionally saves them to user.yaml.`)
}

// ── preset loading ───────────────────────────────────────────────────────────

function loadPreset(name: string): Record<string, any> {
  const files = [
    join(PRESET_DIR, `${name}.yaml`),
    ...['1', '2', '3', '4'].map(n => join(PRESET_DIR, `${n}-${name}.yaml`)),
  ]
  for (const f of files) {
    if (existsSync(f)) return (yaml.load(readFileSync(f, 'utf8')) || {}) as Record<string, any>
  }
  throw new Error(`Preset '${name}' not found in ${PRESET_DIR}/`)
}

// ── user config ───────────────────────────────────────────────────────────────

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

function loadUser(path: string): UserConfig | null {
  if (!existsSync(path)) return null
  return (yaml.load(readFileSync(path, 'utf8')) || {}) as UserConfig
}

// ── interactive wizard ────────────────────────────────────────────────────────

async function runWizard(userPath: string): Promise<string[]> {
  const rl = createInterface({ input: process.stdin, output: process.stdout })
  const subUrls: string[] = []

  const ask = (q: string) => rl.question(q).catch(() => '')

  console.log('\n✨ No subscription URLs found. Enter your proxy airport subscription(s).\n')

  while (true) {
    const url = (await ask('  Subscription URL (empty to finish): ')).trim()
    if (!url) break
    subUrls.push(url)
    console.log(`  ✓ Added (${subUrls.length})`)
  }

  if (subUrls.length > 0) {
    const ans = (await ask(`\n  Save to ${userPath}? [Y/n] `)).trim().toLowerCase()
    if (!ans || ans === 'y') {
      const providerLines = subUrls.map((url, i) =>
        `  - name: "Airport ${i + 1}"\n    url: "${url}"`
      ).join('\n')
      const content = `\
# hajimihomo user configuration
# Edit this file to customize your profile.

# ── proxy subscriptions ───────────────────────────────────────────────────────
proxy_providers:
${providerLines}

# ── preset customization ──────────────────────────────────────────────────────
# target: mihomo         # mihomo (default) | mihomo-smart (vernesong fork)
# topology: regional     # global | regional | advanced (inherits from preset)

# extra_groups: []       # add catalog groups on top of preset
# skip_groups: []        # remove catalog groups from preset

# region_excludes: ""    # regex appended to region filter negations
#                        # e.g. "5x|10x|GB" to exclude bulk-relay nodes

# ── hosts block ───────────────────────────────────────────────────────────────
hosts_enabled: false     # set true to resolve polluted domains via DoH
# hosts_include: []      # opt-in specific domains (empty = all polluted ones)
# hosts_exclude: []      # always skip these domains
`
      mkdirSync(dirname(resolve(userPath)), { recursive: true })
      writeFileSync(userPath, content)
      console.log(`  ✓ Saved to ${userPath}\n`)
    }
  } else {
    console.log('  (no URLs entered — generating profile without proxy providers)\n')
  }

  rl.close()
  return subUrls
}

// ── main ─────────────────────────────────────────────────────────────────────

async function main() {
  const { flags, subs: flagSubs } = parseArgs(process.argv.slice(2))

  const preset = loadPreset(flags.preset)

  // Priority: --sub flags → user.yaml → interactive wizard
  let user: UserConfig = {}
  let subUrls: string[]

  if (flagSubs.length > 0) {
    // flags win; still load file for non-sub settings if it exists
    user = loadUser(flags.user) || {}
    subUrls = flagSubs
  } else {
    const loaded = loadUser(flags.user)
    if (loaded !== null) {
      user = loaded
      subUrls = (user.proxy_providers || []).map((p: any) => p.url).filter(Boolean)
    } else {
      // first-run wizard
      subUrls = await runWizard(flags.user)
    }
  }

  const target   = flags.target   || user.target   || preset.target   || 'mihomo'
  const topology = flags.topology || user.topology  || preset.topology || 'regional'
  const geodata  = flags.geodata  || user.geodata   || 'metacubex'
  const format   = flags.format   || user.format    || 'yaml-split'

  let groupIds: string[] = preset.groups || []
  if (user.extra_groups?.length) groupIds = [...groupIds, ...user.extra_groups]
  if (user.skip_groups?.length) {
    const skip = new Set(user.skip_groups)
    groupIds = groupIds.filter((g: string) => !skip.has(g))
  }

  if (!existsSync(flags.catalog)) {
    console.error(`[error] catalog not found at ${flags.catalog}`)
    console.error(`  Run 'make build-groups' first to generate dist/rulesets.json`)
    process.exit(1)
  }
  const catalog = JSON.parse(readFileSync(flags.catalog, 'utf8'))

  const opts: Record<string, any> = {
    topology, target, format, geodata,
    features: preset.features || {},
    regionExcludes: user.region_excludes || '',
  }

  let profile = buildFullProfile(subUrls, groupIds, catalog, opts)

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

  mkdirSync(flags.output, { recursive: true })
  const outFile = join(flags.output, `${flags.preset}.yaml`)
  writeFileSync(outFile, profile + '\n')
  console.log(`[ok] wrote ${outFile}  (${(profile.length / 1024).toFixed(1)} KB)`)
}

main().catch(e => { console.error(e.message); process.exit(1) })

