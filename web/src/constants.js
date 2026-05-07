// ── Repository / CDN ──────────────────────────────────────────────────────────

export const REPO = 'cest-la-v/hajimihomo'
export const CDN_BASE = `https://cdn.jsdelivr.net/gh/${REPO}`
export const RELEASES_BASE = `https://github.com/${REPO}/releases/latest/download`

// In local dev with RULESET_DIR set, dev.ts proxies /ruleset/mihomo/* from local build.
// Detection: if the page is served from localhost, use a relative URL so the proxy intercepts.
const _isLocal = typeof location !== 'undefined' && location.hostname === 'localhost'
export const RULESETS_URL = _isLocal
  ? '/ruleset/mihomo/rulesets.json'
  : `${CDN_BASE}@ruleset/mihomo/rulesets.json`

// ── Ruleset split types ────────────────────────────────────────────────────────

// Ordering within a group's splits — ip-resolve is handled separately (always last globally)
export const SPLIT_ORDER = ['domain', 'residual', 'process', 'ip']
export const SPLIT_BEHAVIOR = {
  domain:       'domain',
  ip:           'ipcidr',
  'ip-resolve': 'ipcidr',
  residual:     'classical',
  process:      'classical',
}

// ── Geodata sources ────────────────────────────────────────────────────────────

export const GEODATA_SOURCES = {
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

// ── Proxy group configuration ──────────────────────────────────────────────────

// Maps catalog group ID → [display name, preferred region order]
export const SERVICE_MAP = {
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

export const _REGIONS = [
  { name: '香港', pattern: '港|🇭🇰|HK|Hong Kong|HKG' },
  { name: '台湾', pattern: '台|台湾|🇹🇼|TW|TPE|TSA' },
  { name: '狮城', pattern: '坡|新加坡|🇸🇬|SG|Sing|SIN|XSP' },
  { name: '日本', pattern: '日本|日|🇯🇵|JP|Japan|NRT|HND|KIX' },
  { name: '韩国', pattern: '韩|韩国|🇰🇷|KR|Korea|ICN' },
  { name: '美国', pattern: '美|美国|🇺🇸|US|USA|LAX|SJC|JFK|ORD' },
  { name: '欧盟', pattern: '英|法|德|荷|瑞|🇬🇧|🇫🇷|🇩🇪|🇳🇱|🇸🇪|CDG|FRA|AMS|LHR' },
]
export const _FALLBACK_REGIONS = ['香港', '狮城', '日本', '美国']
export const _DIRECT_GROUPS = new Set(['direct/cn', 'direct/cn-ips', 'direct/cn-no-media', 'meta/cn'])
export const _REJECT_GROUPS = new Set(['block/ads', 'block/ads-lite', 'block/tracking', 'meta/block'])

// ── Icons ──────────────────────────────────────────────────────────────────────

export const ICON_BASE = 'https://github.com/Koolson/Qure/raw/master/IconSet/Color'
export const REGION_ICONS = {
  '香港': 'Hong_Kong.png',
  '台湾': 'Taiwan.png',
  '狮城': 'Singapore.png',
  '日本': 'Japan.png',
  '韩国': 'Korea.png',
  '美国': 'United_States.png',
  '欧盟': 'European_Union.png',
}
export const SERVICE_ICONS = {
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

// ── Profile defaults key groups ────────────────────────────────────────────────

export const _CORE_KEYS = [
  'mixed-port', 'allow-lan', 'bind-address', 'mode', 'log-level',
  'ipv6', 'unified-delay', 'tcp-concurrent', 'find-process-mode',
  'global-client-fingerprint', 'global-ua', 'keep-alive-idle', 'keep-alive-interval',
  'etag-support',
  // conditionally present (dashboard feature):
  'external-controller', 'external-ui', 'external-ui-url', 'secret',
  // conditionally present (mihomo-smart target):
  'lgbm-auto-update', 'lgbm-update-interval', 'lgbm-url',
]
export const _GEODATA_KEYS = ['geodata-mode', 'geo-auto-update', 'geo-update-interval', 'geox-url']
