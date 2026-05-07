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

import yaml from 'js-yaml'

const REPO = 'cest-la-v/hajimihomo'
const CDN_BASE = `https://cdn.jsdelivr.net/gh/${REPO}`
// In local dev with RULESET_DIR set, dev.ts proxies /ruleset/mihomo/* from local build.
// Detection: if the page is served from localhost, use a relative URL so the proxy intercepts.
const _isLocal = typeof location !== 'undefined' && location.hostname === 'localhost'
const RULESETS_URL = _isLocal
  ? '/ruleset/mihomo/rulesets.json'
  : `${CDN_BASE}@ruleset/mihomo/rulesets.json`

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

/** @returns {Promise<Object>} presets from gh-pages presets.json (built from profiles/presets/*.yaml) */
export async function loadPresets() {
  const resp = await fetch('presets.json')
  if (!resp.ok) throw new Error(`Failed to load presets: ${resp.status}`)
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
  // Global type buckets — CRITICAL for correct cross-group ordering.
  // Per-group ordering (domain→residual→process→ip per group) is WRONG:
  //   direct-cn-process would precede proxy-telegram-domain, letting process
  //   rules shadow domain policy from later groups.
  // Correct order: ALL .domain → ALL .residual → ALL .process → ALL .ip →
  //                ALL .ip-resolve (LAST — triggers DNS).
  const buckets = { domain: [], residual: [], process: [], ip: [], 'ip-resolve': [] }

  for (const gid of groupIds) {
    const flatName = gid.replace(/\//g, '-')
    const info = (catalog.items || {})[flatName]
    if (!info) continue

    const action       = info.default_action || 'PROXY'
    const mihomoSplits = info.targets?.mihomo?.splits || []
    const useSplits    = tier >= 2 && mihomoSplits.length > 0

    if (!useSplits) {
      // Tier 1: all-in-one classical — goes in domain bucket (first phase)
      providers[flatName] = _provider(flatName, `${flatName}.yaml`, info.behavior || 'classical')
      buckets.domain.push(`RULE-SET,${flatName},${action}`)
    } else {
      // Tier 2: place each split in its global type bucket
      for (const split of [...SPLIT_ORDER, 'ip-resolve']) {
        if (!mihomoSplits.includes(split)) continue
        const key = `${flatName}-${split}`
        providers[key] = _provider(key, `${flatName}.${split}.yaml`, SPLIT_BEHAVIOR[split] || 'ipcidr')
        buckets[split].push(split === 'ip'
          ? `RULE-SET,${key},${action},no-resolve`
          : `RULE-SET,${key},${action}`)
      }
    }
  }

  return {
    providers,
    rules: [
      ...buckets.domain,
      ...buckets.residual,
      ...buckets.process,
      ...buckets.ip,
      ...buckets['ip-resolve'],  // must be absolute last — triggers DNS
    ],
  }
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
  const ruleSets = []
  // Same global bucket pattern as buildRuleProviders — process must follow all domain.
  // sing-box has no no-resolve; ip-resolve bucket stays empty but is kept for symmetry.
  const buckets = { domain: [], residual: [], process: [], ip: [], 'ip-resolve': [] }

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
      buckets.domain.push({ rule_set: tag, outbound })
    } else {
      for (const split of SPLIT_ORDER) {
        if (!sbSplits.includes(split)) continue
        const tag = `ruleset-${flatName}-${split}`
        ruleSets.push(_sbRuleSet(tag, `singbox/${flatName}.${split}.json`))
        buckets[split].push({ rule_set: tag, outbound })
      }
    }
  }

  const routeRules = [
    ...buckets.domain,
    ...buckets.residual,
    ...buckets.process,
    ...buckets.ip,
  ]
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

// ═══════════════════════════════════════════════════════════════════════════════
// COMPLETE PROFILE GENERATION
// ═══════════════════════════════════════════════════════════════════════════════

const RELEASES_BASE = `https://github.com/${REPO}/releases/latest/download`

const GEODATA_SOURCES = {
  metacubex: {
    geosite: 'https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geosite.dat',
    geoip:   'https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip-lite.dat',
    mmdb:    'https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country-lite.mmdb',
    asn:     'https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/GeoLite2-ASN.mmdb',
  },
  dustinwin: {
    geosite: 'https://github.com/DustinWin/ruleset_geodata/releases/download/mihomo-geodata/geosite.dat',
    geoip:   'https://github.com/DustinWin/ruleset_geodata/releases/download/mihomo-geodata/geoip.metadb',
    mmdb:    'https://github.com/DustinWin/ruleset_geodata/releases/download/mihomo-geodata/Country.mmdb',
    asn:     'https://github.com/DustinWin/ruleset_geodata/releases/download/mihomo-geodata/Country-ASN.mmdb',
  },
}

const SERVICE_MAP = {
  'block/ads':          ['🚫 广告拦截',   []],
  'block/ads-lite':     ['🚫 广告(轻)',   []],
  'block/tracking':     ['🕵 追踪拦截',   []],
  'direct/cn':          ['🇨🇳 直连',     []],
  'direct/cn-ips':      ['🇨🇳 直连IP',   []],
  'direct/cn-no-media': ['🇨🇳 直连(无媒体)', []],
  'proxy/google':       ['🔍 Google',    ['香港', '美国', '默认代理']],
  'proxy/youtube':      ['▶️  YouTube',   ['香港', '美国', '默认代理']],
  'proxy/apple':        ['🍎 Apple',     ['直接连接', '香港', '美国']],
  'proxy/microsoft':    ['🪟 Microsoft', ['默认代理', '直接连接']],
  'proxy/amazon':       ['📦 Amazon',    ['美国', '默认代理']],
  'proxy/telegram':     ['✈️  Telegram',  ['香港', '狮城', '默认代理']],
  'proxy/twitter':      ['🐦 Twitter',   ['香港', '美国', '默认代理']],
  'proxy/netflix':      ['🎬 Netflix',   ['狮城', '香港', '默认代理']],
  'proxy/streaming':    ['🎥 Streaming', ['狮城', '香港', '默认代理']],
  'proxy/social':       ['💬 Social',    ['香港', '默认代理']],
  'proxy/ai':           ['🤖 AI',        ['美国', '默认代理']],
  'proxy/gaming':       ['🎮 Gaming',    ['香港', '日本', '默认代理']],
  'proxy/dev':          ['💻 Dev',       ['默认代理', '直接连接']],
  'proxy/finance':      ['💰 Finance',   ['香港', '默认代理']],
  'proxy/news':         ['📰 News',      ['默认代理']],
  'meta/block':         ['🚫 Meta拦截',  []],
  'meta/cn':            ['🇨🇳 Meta直连', []],
  'meta/foreign':       ['🌐 Meta外网',  ['默认代理']],
}

const _REGIONS = [
  { name: '香港', pattern: '港|🇭🇰|HK|Hong Kong|HKG' },
  { name: '台湾', pattern: '台|台湾|🇹🇼|TW|TPE|TSA' },
  { name: '狮城', pattern: '坡|新加坡|🇸🇬|SG|Sing|SIN|XSP' },
  { name: '日本', pattern: '日本|日|🇯🇵|JP|Japan|NRT|HND|KIX' },
  { name: '韩国', pattern: '韩|韩国|🇰🇷|KR|Korea|ICN' },
  { name: '美国', pattern: '美|美国|🇺🇸|US|USA|LAX|SJC|JFK|ORD' },
  { name: '欧盟', pattern: '英|法|德|荷|瑞|🇬🇧|🇫🇷|🇩🇪|🇳🇱|🇸🇪|CDG|FRA|AMS|LHR' },
]
const _FALLBACK_REGIONS = ['香港', '狮城', '日本', '美国']
const _DIRECT_GROUPS = new Set(['direct/cn', 'direct/cn-ips', 'direct/cn-no-media', 'meta/cn'])
const _REJECT_GROUPS = new Set(['block/ads', 'block/ads-lite', 'block/tracking', 'meta/block'])

const ICON_BASE = 'https://github.com/Koolson/Qure/raw/master/IconSet/Color'
const REGION_ICONS = {
  '香港': 'Hong_Kong.png',
  '台湾': 'Taiwan.png',
  '狮城': 'Singapore.png',
  '日本': 'Japan.png',
  '韩国': 'Korea.png',
  '美国': 'United_States.png',
  '欧盟': 'European_Union.png',
}
const SERVICE_ICONS = {
  'proxy/google':    'Google.png',
  'proxy/youtube':   'YouTube.png',
  'proxy/apple':     'Apple.png',
  'proxy/microsoft': 'Microsoft.png',
  'proxy/amazon':    'Amazon.png',
  'proxy/telegram':  'Telegram.png',
  'proxy/twitter':   'Twitter.png',
  'proxy/netflix':   'Netflix.png',
  'proxy/streaming': 'Streaming.png',
  'proxy/ai':        'AI.png',
  'proxy/gaming':    'Gaming.png',
}

function _slug2(gid) { return gid.replace(/\//g, '-') }
function _autoType(target) { return target === 'mihomo-smart' ? 'smart' : 'url-test' }
function _regionFilter(pattern, exclude) {
  const neg = exclude ? `(?!.*(?:${exclude}))` : ''
  return `^(?=.*(?i)(${pattern}))${neg}.*$`
}
function _dump(obj) { return yaml.dump(obj, { indent: 2, lineWidth: -1, noRefs: true }).trimEnd() }

function _buildProxyGroups(groupIds, { topology, target, features, regionExcludes }) {
  const groups = []
  const autoType = _autoType(target)
  const autoProps = autoType === 'url-test'
    ? { url: 'https://www.google.com/generate_204', interval: 200 }
    : { uselightgbm: true }
  const regionNames = _REGIONS.map(r => r.name)
  const rejectGroups  = groupIds.filter(g => _REJECT_GROUPS.has(g))
  const serviceGroups = groupIds.filter(g => !_DIRECT_GROUPS.has(g) && !_REJECT_GROUPS.has(g))

  // ── infrastructure ──────────────────────────────────────────────────────────
  if (topology === 'global') {
    groups.push({ name: '默认代理', type: 'select', proxies: ['全部', '直接连接'], icon: `${ICON_BASE}/Proxy.png` })
  } else {
    groups.push({
      name: '默认代理', type: 'select',
      proxies: ['故障转移', ...regionNames, '全部', '直接连接'],
      icon: `${ICON_BASE}/Proxy.png`,
    })
    const fbCandidates = _FALLBACK_REGIONS.filter(r => regionNames.includes(r))
    groups.push({
      name: '故障转移', type: 'fallback',
      url: 'https://www.google.com/generate_204', interval: 200, lazy: true,
      proxies: fbCandidates,
      icon: `${ICON_BASE}/Available.png`,
    })
  }
  groups.push({ name: '直接连接', type: 'select', proxies: ['DIRECT', '默认代理'], icon: `${ICON_BASE}/Direct.png` })

  // ── block groups (named select — never hardcode REJECT in rules) ────────────
  for (const gid of rejectGroups) {
    const name = (SERVICE_MAP[gid] || [`🚫 ${gid.split('/')[1]}`])[0]
    groups.push({ name, type: 'select', proxies: ['REJECT', 'DIRECT', '默认代理'] })
  }
  if (features?.quic_block)
    groups.push({ name: '🛡️ 协议拦截', type: 'select', proxies: ['REJECT', 'DIRECT', '默认代理'] })

  // ── region groups ───────────────────────────────────────────────────────────
  if (topology !== 'global') {
    for (const r of _REGIONS) {
      const filter = _regionFilter(r.pattern, regionExcludes)
      if (topology === 'advanced' && features?.load_balance) {
        groups.push({
          name: `${r.name}-LBH`, type: 'load-balance', strategy: 'consistent-hashing',
          url: 'https://www.google.com/generate_204', interval: 200, lazy: true, hidden: true,
          'include-all': true, filter,
        })
        groups.push({
          name: `${r.name}-LBR`, type: 'load-balance', strategy: 'round-robin',
          url: 'https://www.google.com/generate_204', interval: 200, lazy: true, hidden: true,
          'include-all': true, filter,
        })
      }
      const g = { name: r.name, type: autoType, ...autoProps, lazy: true, 'include-all': true, filter }
      if (REGION_ICONS[r.name]) g.icon = `${ICON_BASE}/${REGION_ICONS[r.name]}`
      groups.push(g)
    }
  }
  // global auto (hidden)
  groups.push({ name: '全部', type: autoType, ...autoProps, lazy: true, hidden: true, 'include-all': true })

  // ── per-service groups ──────────────────────────────────────────────────────
  const effectiveMap = {}
  for (const gid of serviceGroups) {
    const entry = SERVICE_MAP[gid]
    const displayName = entry ? entry[0] : `🌐 ${gid.split('/')[1]}`
    const preferred   = entry ? entry[1] : []
    let candidates
    if (topology !== 'global') {
      candidates = preferred.filter(p => regionNames.includes(p) || p === '默认代理' || p === '直接连接')
      if (!candidates.length) candidates = ['默认代理', '直接连接']
      if (!candidates.includes('默认代理')) candidates.push('默认代理')
    } else {
      candidates = ['默认代理', '直接连接']
    }
    effectiveMap[gid] = [displayName, candidates]
    const g = { name: displayName, type: 'select', proxies: candidates }
    if (SERVICE_ICONS[gid]) g.icon = `${ICON_BASE}/${SERVICE_ICONS[gid]}`
    groups.push(g)
  }
  groups.push({ name: '漏网之鱼', type: 'select', proxies: ['默认代理', '直接连接'], icon: `${ICON_BASE}/Proxy.png` })
  return { groups, effectiveMap }
}

function _needsIpProvider2(gid, catalog) {
  if (gid === 'direct/cn-ips') return true
  if (_DIRECT_GROUPS.has(gid)) return false
  const info = (catalog?.items || {})[_slug2(gid)]
  if (!info) return true
  const splits = info.targets?.mihomo?.splits || []
  return splits.includes('ip') || splits.includes('ip-resolve')
}

function _buildRuleProvidersForFormat(groupIds, catalog, format = 'yaml-split') {
  const providers = {}
  const RULESET_CDN = `${CDN_BASE}@ruleset/mihomo`

  for (const gid of groupIds) {
    const s = _slug2(gid)

    if (format === 'yaml-classical') {
      providers[s] = {
        type: 'http', behavior: 'classical',
        url: `${RULESET_CDN}/${s}.yaml`,
        path: `./ruleset/${s}.yaml`,
        interval: 86400, format: 'yaml',
      }
    } else if (format === 'binary') {
      if (gid !== 'direct/cn-ips') {
        providers[s] = {
          type: 'http', behavior: 'domain',
          url: `${RELEASES_BASE}/${s}.domain.mrs`,
          path: `./ruleset/${s}.domain.mrs`,
          interval: 86400, format: 'mrs',
        }
      }
      if (_needsIpProvider2(gid, catalog)) {
        providers[`${s}-ip`] = {
          type: 'http', behavior: 'ipcidr',
          url: `${RELEASES_BASE}/${s}.ip.mrs`,
          path: `./ruleset/${s}.ip.mrs`,
          interval: 86400, format: 'mrs',
        }
      }
    } else {
      // yaml-split (default)
      if (gid !== 'direct/cn-ips') {
        providers[s] = {
          type: 'http', behavior: 'domain',
          url: `${RULESET_CDN}/${s}.domain.yaml`,
          path: `./ruleset/${s}.domain.yaml`,
          interval: 86400, format: 'yaml',
        }
      }
      if (_needsIpProvider2(gid, catalog)) {
        providers[`${s}-ip`] = {
          type: 'http', behavior: 'ipcidr',
          url: `${RULESET_CDN}/${s}.ip.yaml`,
          path: `./ruleset/${s}.ip.yaml`,
          interval: 86400, format: 'yaml',
        }
      }
    }
  }
  return providers
}

function _buildRules2(groupIds, catalog, effectiveMap, features, format = 'yaml-split') {
  const rules = []
  const isSplit = format !== 'yaml-classical'

  if (features?.quic_block)
    rules.push('AND,((DST-PORT,443),(NETWORK,UDP),(NOT,((GEOIP,CN)))),🛡️ 协议拦截')

  // block groups → named proxy group (never hardcode REJECT)
  for (const gid of groupIds)
    if (_REJECT_GROUPS.has(gid)) {
      const name = (SERVICE_MAP[gid] || [`🚫 ${gid.split('/')[1]}`])[0]
      rules.push(`RULE-SET,${_slug2(gid)},${name}`)
    }

  // direct domain groups (cn-ips handled separately — IP only)
  for (const gid of groupIds)
    if (_DIRECT_GROUPS.has(gid) && gid !== 'direct/cn-ips')
      rules.push(`RULE-SET,${_slug2(gid)},DIRECT`)

  // service groups
  for (const gid of groupIds) {
    if (_DIRECT_GROUPS.has(gid) || _REJECT_GROUPS.has(gid)) continue
    rules.push(`RULE-SET,${_slug2(gid)},${(effectiveMap[gid] || [_slug2(gid)])[0]}`)
  }

  // IP rules (split formats only — separate -ip provider; classical has IP in main file)
  if (isSplit) {
    for (const gid of groupIds)
      if (gid === 'direct/cn-ips')
        rules.push(`RULE-SET,${_slug2(gid)}-ip,DIRECT,no-resolve`)
    for (const gid of groupIds) {
      if (_DIRECT_GROUPS.has(gid) || _REJECT_GROUPS.has(gid)) continue
      if (_needsIpProvider2(gid, catalog))
        rules.push(`RULE-SET,${_slug2(gid)}-ip,${(effectiveMap[gid] || [_slug2(gid)])[0]},no-resolve`)
    }
  } else {
    // classical: cn-ips IP rules are in the single file; no-resolve still applies
    for (const gid of groupIds)
      if (gid === 'direct/cn-ips')
        rules.push(`RULE-SET,${_slug2(gid)},DIRECT,no-resolve`)
  }

  rules.push('MATCH,漏网之鱼')
  return rules
}

function _proxyProviders2(subUrls) {
  const FILTER = '^(?!.*(群|订阅|到期|流量|机场|官网|邮箱|通知|Panel|Author|TOTAL|EXPIRE)).*$'
  if (!subUrls.length) return {}
  const providers = {}
  subUrls.forEach((url, i) => {
    providers[`airport-${i + 1}`] = {
      type: 'http',
      interval: 86400,
      proxy: 'DIRECT',
      'health-check': { enable: true, url: 'https://www.google.com/generate_204', interval: 300 },
      filter: FILTER,
      url,
    }
  })
  return providers
}

const _core = (target, features = {}) => {
  const parts = [
`mixed-port: 7890
allow-lan: false
bind-address: '*'
mode: rule
log-level: warning
ipv6: true
unified-delay: true
tcp-concurrent: true
find-process-mode: strict
global-client-fingerprint: chrome
global-ua: mihomo
keep-alive-idle: 600
keep-alive-interval: 60
etag-support: true`]
  if (features.dashboard) parts.push(
`external-controller: ':9090'
external-ui: ui
external-ui-url: 'https://github.com/MetaCubeX/metacubexd/archive/refs/heads/gh-pages.zip'
secret: ''`)
  if (target === 'mihomo-smart') parts.push(
`lgbm-auto-update: true
lgbm-update-interval: 24
lgbm-url: 'https://github.com/vernesong/mihomo/releases/download/LightGBM-Model/Model-large.bin'`)
  return parts.join('\n')
}

const _geodata = (geodata = 'metacubex') => {
  const u = GEODATA_SOURCES[geodata] || GEODATA_SOURCES.metacubex
  return `\
geodata-mode: true
geo-auto-update: true
geo-update-interval: 168
geox-url:
  geoip: '${u.geoip}'
  geosite: '${u.geosite}'
  mmdb: '${u.mmdb}'
  asn: '${u.asn}'`
}

const _profile = (target) =>
`profile:
  store-selected: true
  store-fake-ip: true${target === 'mihomo-smart' ? '\n  smart-collector-size: 1024' : ''}`

const _dns = () =>
`dns:
  enable: true
  ipv6: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  fake-ip-range6: 3fff::/20
  fake-ip-filter-mode: blacklist
  fake-ip-filter:
    - '*.lan'
    - '*.local'
    - '*.localhost'
    - '*.home.arpa'
    - '+.stun.*.*'
    - '+.stun.*.*.*'
    - '+.stun.*.*.*.*'
    - 'time.*.com'
    - 'time.*.gov'
    - 'time.*.apple.com'
    - '+.ntp.org.cn'
    - '+.time.edu.cn'
    - 'ntp.ubuntu.com'
    - 'time.cloudflare.com'
    - '+.pool.ntp.org'
    - '+.msftconnecttest.com'
    - '+.msftncsi.com'
    - '+.push.apple.com'
    - 'swcd.*.apple.com'
    - 'mesu.apple.com'
    - '+.miwifi.com'
    - '+.docker.io'
    - '+.xbox.com'
    - '+.xboxlive.com'
  cache-algorithm: arc
  respect-rules: false
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  nameserver:
    - https://doh.pub/dns-query
    - https://dns.alidns.com/dns-query
  fallback:
    - https://1.1.1.1/dns-query
    - https://8.8.8.8/dns-query
    - https://9.9.9.9/dns-query
  fallback-filter:
    geoip: true
    geoip-code: CN
    ipcidr:
      - 240.0.0.0/4`

const _sniffer = () =>
`sniffer:
  enable: true
  sniff:
    HTTP:
      ports: [80, 8080-8880]
      override-destination: true
    TLS:
      ports: [443, 8443]
    QUIC:
      ports: [443, 8443]
  skip-domain:
    - 'Mijia Cloud'
    - '+.push.apple.com'`

const _tun = (tun_enable = false) => tun_enable
  ? `tun:
  enable: true
  stack: mixed
  auto-route: true
  auto-redirect: true
  auto-detect-interface: true
  dns-hijack:
    - any:53`
  : `# tun:
#   enable: false
#   stack: mixed
#   auto-route: true
#   auto-redirect: true
#   auto-detect-interface: true
#   dns-hijack:
#     - any:53`

/**
 * Build a complete standalone mihomo YAML profile.
 *
 * @param {string[]} subUrls       — subscription URLs
 * @param {string[]} groupIds      — selected catalog group IDs
 * @param {Object}   catalog       — from loadCatalog()
 * @param {Object}   opts
 * @param {string}   opts.topology — 'advanced' | 'regional' | 'global'
 * @param {string}   opts.target   — 'mihomo' | 'mihomo-smart'
 * @param {Object}   opts.features — { ads_block, quic_block, load_balance, ... }
 * @param {string}   opts.regionExcludes — regex negated in region filters
 * @returns {string} complete YAML profile
 */
export function buildFullProfile(subUrls, groupIds, catalog, opts = {}) {
  const {
    topology = 'regional',
    target = 'mihomo',
    features = {},
    regionExcludes = '',
    geodata = 'metacubex',
    format = 'yaml-split',
  } = opts

  const { groups, effectiveMap } = _buildProxyGroups(groupIds, { topology, target, features, regionExcludes })
  const ruleProviders = _buildRuleProvidersForFormat(groupIds, catalog, format)
  const rules         = _buildRules2(groupIds, catalog, effectiveMap, features, format)
  const proxyProviders = _proxyProviders2(subUrls)

  const header = target === 'mihomo-smart'
    ? '# ⚠️  Requires vernesong/mihomo fork — https://github.com/vernesong/mihomo'
    : '# generated by hajimihomo · https://github.com/cest-la-v/hajimihomo'

  const sections = [
    `${header}\n# topology: ${topology}  target: ${target}  groups: ${groupIds.length}`,
    _core(target, features),
    _geodata(geodata),
    _profile(target),
    _dns(),
    _sniffer(),
    _tun(features.tun_enable),
    `# ── proxy providers ──────────────────────────────────────────────────────────\n` +
      (subUrls.length
        ? _dump({ 'proxy-providers': proxyProviders })
        : `# proxy-providers:\n#   airport-1:\n#     type: http\n#     url: 'https://your-airport.com/subscribe?token=xxx'\nproxy-providers: {}`),
    `# ── proxy groups ─────────────────────────────────────────────────────────────\n` +
      _dump({ 'proxy-groups': groups }),
    `# ── rule providers ───────────────────────────────────────────────────────────\n` +
      _dump({ 'rule-providers': ruleProviders }),
    `# ── rules ────────────────────────────────────────────────────────────────────\n` +
      _dump({ rules }),
  ]

  return sections.join('\n\n')
}
