/**
 * Profile builder core.
 *
 * Reads rulesets.json (emitted by build.py, served on the ruleset/mihomo branch)
 * and assembles a mihomo or sing-box config fragment from user-selected catalog groups.
 *
 * Catalog group IDs use slash notation (e.g. 'proxy/telegram').
 * Flat file-stem names are derived by replacing '/' with '-' (e.g. 'proxy-telegram').
 *
 * Tier 1 — classical all-in-one: one file per group, broadest compatibility.
 * Tier 2 — split files: separate domain/ip/residual/process files for performance.
 *           ip-resolve files are appended LAST across all groups (DNS safety).
 *           .ip providers require the no-resolve flag on the RULE-SET entry.
 *
 * Do NOT mix Tier-1 and Tier-2 files for the same category.
 *
 * sing-box output is a route/rule_set fragment only — subscription handling
 * is outside scope (use a kernel-level subscription import for outbounds).
 */

const REPO = 'cest-la-v/hajimihomo'
const CDN_BASE = `https://cdn.jsdelivr.net/gh/${REPO}`
const RULESETS_URL = `${CDN_BASE}@ruleset/mihomo/rulesets.json`

// Ordering within a group's splits — ip-resolve is handled separately (always last globally)
const SPLIT_ORDER = ['domain', 'residual', 'process', 'ip']
const SPLIT_BEHAVIOR = {
  domain:       'domain',
  ip:           'ipcidr',
  'ip-resolve': 'ipcidr',
  residual:     'classical',
  process:      'classical',
}

/** @returns {Promise<Object>} rulesets manifest from build.py */
export async function loadCatalog() {
  const resp = await fetch(RULESETS_URL)
  if (!resp.ok) throw new Error(`Failed to load catalog: ${resp.status}`)
  return resp.json()
}

/**
 * List available catalog groups from rulesets.json, sorted by group ID.
 * @param {Object} catalog — from loadCatalog()
 * @returns {{ id, flatName, name, defaultAction, region, tags }[]}
 */
export function getGroups(catalog) {
  return Object.entries(catalog.items || {})
    .filter(([, info]) => info.kind === 'group')
    .map(([flatName, info]) => ({
      id:            info.group_id,
      flatName,
      name:          info.name || flatName,
      defaultAction: info.default_action || 'PROXY',
      region:        info.region || 'any',
      tags:          info.tags || [],
    }))
    .sort((a, b) => a.id.localeCompare(b.id))
}

/**
 * Build mihomo rule-providers + ordered rules for selected catalog groups.
 *
 * @param {string[]} groupIds — catalog group IDs (e.g. ['proxy/telegram', 'block/ads'])
 * @param {Object}   catalog  — from loadCatalog()
 * @param {{tier?: number}} options  — tier 1 (default) or 2
 * @returns {{ providers: Object, rules: string[] }}
 */
export function buildRuleProviders(groupIds, catalog, { tier = 1 } = {}) {
  const providers = {}
  const regularRules   = []
  const ipResolveRules = []  // collected separately; appended LAST

  for (const gid of groupIds) {
    const flatName = gid.replace(/\//g, '-')
    const info = (catalog.items || {})[flatName]
    if (!info) continue

    const action       = info.default_action || 'PROXY'
    const mihomoSplits = info.targets?.mihomo?.splits || []
    const useSplits    = tier >= 2 && mihomoSplits.length > 0

    if (!useSplits) {
      // Tier 1: all-in-one classical file
      providers[flatName] = _provider(flatName, `${flatName}.yaml`, info.behavior || 'classical')
      regularRules.push(`RULE-SET,${flatName},${action}`)
    } else {
      // Tier 2: splits in canonical order
      for (const split of SPLIT_ORDER) {
        if (!mihomoSplits.includes(split)) continue
        const key = `${flatName}-${split}`
        providers[key] = _provider(key, `${flatName}.${split}.yaml`, SPLIT_BEHAVIOR[split])
        // .ip has no-resolve: triggers no DNS resolution, safe anywhere in list
        regularRules.push(split === 'ip'
          ? `RULE-SET,${key},${action},no-resolve`
          : `RULE-SET,${key},${action}`)
      }
      // ip-resolve: triggers DNS — must be absolute last across all groups
      if (mihomoSplits.includes('ip-resolve')) {
        const key = `${flatName}-ip-resolve`
        providers[key] = _provider(key, `${flatName}.ip-resolve.yaml`, 'ipcidr')
        ipResolveRules.push(`RULE-SET,${key},${action}`)
      }
    }
  }

  return { providers, rules: [...regularRules, ...ipResolveRules] }
}

function _provider(name, filename, behavior) {
  return {
    type:     'http',
    behavior,
    url:      `${CDN_BASE}@ruleset/mihomo/${filename}`,
    path:     `./ruleset/${filename}`,
    interval: 86400,
    format:   'yaml',
  }
}

/**
 * Build sing-box route rule_set entries for selected catalog groups.
 * Tier 1: {flatName}.json   Tier 2: {flatName}.{split}.json
 * No ip-resolve split — sing-box has no no-resolve concept; .ip covers all IP-CIDR.
 *
 * @returns {{ ruleSets: Object[], routeRules: Object[] }}
 */
export function buildSingboxRuleSets(groupIds, catalog, { tier = 1 } = {}) {
  const ruleSets   = []
  const routeRules = []

  for (const gid of groupIds) {
    const flatName = gid.replace(/\//g, '-')
    const info = (catalog.items || {})[flatName]
    if (!info) continue

    const action   = info.default_action || 'PROXY'
    const outbound = action === 'REJECT' ? 'block' : action.toLowerCase()
    const sbSplits = info.targets?.singbox?.splits || []
    const useSplits = tier >= 2 && sbSplits.length > 0

    if (!useSplits) {
      const tag = `ruleset-${flatName}`
      ruleSets.push(_sbRuleSet(tag, `singbox/${flatName}.json`))
      routeRules.push({ rule_set: tag, outbound })
    } else {
      for (const split of SPLIT_ORDER) {
        if (!sbSplits.includes(split)) continue
        const tag = `ruleset-${flatName}-${split}`
        ruleSets.push(_sbRuleSet(tag, `singbox/${flatName}.${split}.json`))
        routeRules.push({ rule_set: tag, outbound })
      }
    }
  }

  return { ruleSets, routeRules }
}

function _sbRuleSet(tag, path) {
  return {
    tag,
    type:             'remote',
    format:           'source',
    url:              `${CDN_BASE}@ruleset/${path}`,
    download_detour:  'proxy',
    update_interval:  '1d',
  }
}

/**
 * Assemble a mihomo config fragment: proxy-providers, proxy-groups, rule-providers, rules.
 *
 * @param {string[]} subUrls  — subscription URLs
 * @param {string[]} groupIds — selected catalog group IDs
 * @param {Object}   catalog
 * @param {{tier?: number}} options
 * @returns {{ proxyProviders, groups, providers, rules }}
 */
export function buildMihomoGroups(subUrls, groupIds, catalog, { tier = 1 } = {}) {
  const providerNames = subUrls.map((_, i) => `sub-${i + 1}`)
  const proxyProviders = {}
  subUrls.forEach((url, i) => {
    proxyProviders[`sub-${i + 1}`] = {
      type: 'http',
      url,
      interval: 3600,
      health_check: { enable: true, url: 'https://cp.cloudflare.com', interval: 300 },
    }
  })

  const groups = [
    { name: 'PROXY',  type: 'select',   use: providerNames, proxies: ['AUTO', 'DIRECT'] },
    { name: 'AUTO',   type: 'url-test', use: providerNames,
      url: 'https://cp.cloudflare.com', interval: 300, tolerance: 50 },
    { name: 'DIRECT', type: 'select',   proxies: ['DIRECT'] },
    { name: 'REJECT', type: 'select',   proxies: ['REJECT'] },
  ]

  const { providers, rules } = buildRuleProviders(groupIds, catalog, { tier })
  return { proxyProviders, groups, providers, rules }
}
