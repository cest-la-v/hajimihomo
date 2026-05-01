/**
 * Profile builder core.
 *
 * Reads rulesets.json catalog (built by build.py alongside rule-set outputs)
 * and assembles a mihomo or sing-box config from user selections.
 */

const REPO = 'cest-la-v/hajimihomo'
const RAW_BASE = `https://raw.githubusercontent.com/${REPO}`
const CDN_BASE = `https://cdn.jsdelivr.net/gh/${REPO}`
const RELEASES_BASE = `https://github.com/${REPO}/releases/latest/download`
const RULESETS_URL = `${CDN_BASE}@ruleset/mihomo/rulesets.json`

/** @returns {Promise<Object>} rulesets catalog */
export async function loadCatalog() {
  const resp = await fetch(RULESETS_URL)
  if (!resp.ok) throw new Error(`Failed to load catalog: ${resp.status}`)
  return resp.json()
}

/**
 * Build mihomo rule-providers block for selected categories.
 * @param {string[]} categories
 * @param {Object} catalog  — from loadCatalog()
 * @returns {Object}  — proxy-friendly object for YAML serialization
 */
export function buildRuleProviders(categories, catalog) {
  const providers = {}
  for (const cat of categories) {
    const info = catalog[cat]
    if (!info) continue
    const url = `${CDN_BASE}@ruleset/mihomo/${cat}.yaml`
    providers[cat] = {
      type: 'http',
      behavior: info.behavior || 'classical',
      url,
      path: `./ruleset/${cat}.yaml`,
      interval: 86400,
      format: 'yaml',
    }
  }
  return providers
}

/**
 * Build sing-box route rule_set entries for selected categories.
 * @param {string[]} categories
 * @returns {Object[]}
 */
export function buildSingboxRuleSets(categories) {
  return categories.map(cat => ({
    tag: `ruleset-${cat}`,
    type: 'remote',
    format: 'binary',
    url: `${RELEASES_BASE}/${cat}.srs`,
    download_detour: 'proxy',
    update_interval: '1d',
  }))
}

/**
 * Assemble mihomo proxy-groups from subscription URLs and selected categories.
 * Pattern inspired by 666OS/YYDS: auto-select + URL-test fallback.
 *
 * @param {string[]} subUrls — subscription URLs
 * @param {string[]} categories — selected rule categories
 * @param {Object} catalog
 * @returns {{ groups: Object[], rules: string[] }}
 */
export function buildMihomoGroups(subUrls, categories, catalog) {
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
    {
      name: 'PROXY',
      type: 'select',
      use: providerNames,
      proxies: ['AUTO', 'DIRECT'],
    },
    {
      name: 'AUTO',
      type: 'url-test',
      use: providerNames,
      url: 'https://cp.cloudflare.com',
      interval: 300,
      tolerance: 50,
    },
    {
      name: 'DIRECT',
      type: 'select',
      proxies: ['DIRECT'],
    },
    {
      name: 'REJECT',
      type: 'select',
      proxies: ['REJECT'],
    },
  ]

  // categorise rule categories into routing buckets
  const BLOCK_CATS = new Set(['Advertising', 'Privacy', 'Hijacking'])
  const DIRECT_CATS = new Set(['China', 'ChinaMedia', 'Microsoft'])

  const rules = []
  for (const cat of categories) {
    const group = BLOCK_CATS.has(cat) ? 'REJECT'
      : DIRECT_CATS.has(cat) ? 'DIRECT'
      : 'PROXY'
    rules.push(`RULE-SET,${cat},${group}`)
  }
  rules.push('GEOIP,CN,DIRECT')
  rules.push('MATCH,PROXY')

  return { proxyProviders, groups, rules }
}
