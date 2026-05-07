/**
 * DoH-based hosts block builder.
 *
 * Resolves DNS-polluted domains via Cloudflare/Google/Quad9 DoH,
 * cross-validates (requires ≥2/3 agreement), and emits a `hosts:` YAML block.
 *
 * Results are cached to source/hosts/.cache.json (keyed by domain+date).
 * source/hosts/overrides.yaml takes precedence — no re-query for those domains.
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import yaml from 'js-yaml'

const POLLUTED_FILE  = 'source/hosts/polluted.yaml'
const OVERRIDES_FILE = 'source/hosts/overrides.yaml'
const CACHE_FILE     = 'source/hosts/.cache.json'

const DOH_PROVIDERS = [
  'https://cloudflare-dns.com/dns-query',
  'https://dns.google/resolve',
  'https://dns.quad9.net:5053/dns-query',
]

interface PollutedEntry {
  domain: string
  enabled: boolean
  category?: string
  notes?: string
}

interface HostsOpts {
  include?: string[]
  exclude?: string[]
}

// ── DoH query ────────────────────────────────────────────────────────────────

async function queryDoh(providerUrl: string, domain: string): Promise<string[]> {
  try {
    const url = `${providerUrl}?name=${encodeURIComponent(domain)}&type=A`
    const resp = await fetch(url, {
      headers: { Accept: 'application/dns-json' },
      signal: AbortSignal.timeout(5000),
    })
    if (!resp.ok) return []
    const data = await resp.json() as { Answer?: Array<{ type: number; data: string }> }
    return (data.Answer || [])
      .filter(r => r.type === 1)  // A record
      .map(r => r.data)
  } catch {
    return []
  }
}

/** Retry with 2 attempts */
async function queryDohWithRetry(provider: string, domain: string): Promise<string[]> {
  for (let i = 0; i < 2; i++) {
    const ips = await queryDoh(provider, domain)
    if (ips.length) return ips
  }
  return []
}

/** Cross-validate across providers: return IPs agreed on by ≥2/3. */
async function resolveWithValidation(domain: string): Promise<string | null> {
  const results = await Promise.all(DOH_PROVIDERS.map(p => queryDohWithRetry(p, domain)))

  // count how many providers returned each IP
  const counts = new Map<string, number>()
  for (const ipList of results) {
    const seen = new Set(ipList)
    for (const ip of seen) counts.set(ip, (counts.get(ip) || 0) + 1)
  }

  // pick IPs agreed on by ≥2 providers (prefer first confirmed IP)
  for (const ipList of results) {
    for (const ip of ipList) {
      if ((counts.get(ip) || 0) >= 2) return ip
    }
  }

  return null  // no consensus
}

// ── cache ─────────────────────────────────────────────────────────────────────

type Cache = Record<string, { ip: string; date: string }>

function loadCache(): Cache {
  if (!existsSync(CACHE_FILE)) return {}
  try { return JSON.parse(readFileSync(CACHE_FILE, 'utf8')) } catch { return {} }
}

function saveCache(cache: Cache) {
  writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2))
}

function cacheKey(domain: string): string {
  return `${domain}:${new Date().toISOString().slice(0, 10)}`
}

// ── main entry ────────────────────────────────────────────────────────────────

/**
 * Build a `hosts:` YAML block from DoH resolution of polluted domains.
 * Returns empty string if no domains are enabled.
 */
export async function buildHostsBlock(opts: HostsOpts = {}): Promise<string> {
  if (!existsSync(POLLUTED_FILE)) {
    console.warn(`[hosts] ${POLLUTED_FILE} not found — skipping hosts block`)
    return ''
  }

  const polluted = (yaml.load(readFileSync(POLLUTED_FILE, 'utf8')) as PollutedEntry[]) || []
  const overrides: Record<string, string> = existsSync(OVERRIDES_FILE)
    ? (yaml.load(readFileSync(OVERRIDES_FILE, 'utf8')) as Record<string, string>) || {}
    : {}

  const includeSet = new Set(opts.include || [])
  const excludeSet = new Set(opts.exclude || [])

  // select domains to resolve
  const selected = polluted.filter(entry => {
    if (excludeSet.has(entry.domain)) return false
    if (includeSet.size > 0) return includeSet.has(entry.domain) || entry.enabled
    return entry.enabled
  })

  if (!selected.length) return ''

  const cache = loadCache()
  const resolved: Record<string, string> = {}
  let cacheHits = 0, queries = 0, failed = 0
  let cacheUpdated = false

  for (const entry of selected) {
    const d = entry.domain

    // overrides take priority — no DoH needed
    if (overrides[d]) {
      resolved[d] = overrides[d]
      continue
    }

    const key = cacheKey(d)
    if (cache[key]) {
      resolved[d] = cache[key].ip
      cacheHits++
      continue
    }

    queries++
    process.stderr.write(`[hosts] resolving ${d}...`)
    const ip = await resolveWithValidation(d)
    if (ip) {
      resolved[d] = ip
      cache[key] = { ip, date: new Date().toISOString().slice(0, 10) }
      cacheUpdated = true
      process.stderr.write(` ${ip}\n`)
    } else {
      failed++
      process.stderr.write(` no consensus — skipped\n`)
    }
  }

  if (cacheUpdated) saveCache(cache)
  if (queries || cacheHits || failed) {
    console.error(`[hosts] ${Object.keys(resolved).length} resolved (${cacheHits} cached, ${queries} queried, ${failed} failed)`)
  }

  if (!Object.keys(resolved).length) return ''

  // group by category
  const byCategory: Record<string, Array<[string, string]>> = {}
  for (const entry of selected) {
    const ip = resolved[entry.domain]
    if (!ip) continue
    const cat = entry.category || 'misc'
    if (!byCategory[cat]) byCategory[cat] = []
    byCategory[cat].push([entry.domain, ip])
  }

  const lines = ['hosts:']
  for (const [cat, entries] of Object.entries(byCategory)) {
    lines.push(`  # ${cat} (updated: ${new Date().toISOString().slice(0, 10)})`)
    for (const [domain, ip] of entries) lines.push(`  '${domain}': '${ip}'`)
  }

  return lines.join('\n')
}
