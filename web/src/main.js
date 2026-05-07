import { loadCatalog, loadPresets, getGroups, buildSingboxRuleSets, buildFullProfile } from './ProfileBuilder.js'

const app = document.getElementById('app')

app.innerHTML = `
  <div class="section">
    <label>内核 / 输出格式</label>
    <select id="kernel">
      <option value="mihomo">mihomo (Clash Meta) — 完整配置</option>
      <option value="mihomo-smart">mihomo-smart (vernesong fork) — 完整配置 + smart 分组</option>
      <option value="singbox">sing-box — 路由规则片段</option>
    </select>
  </div>

  <div class="section" id="topology-section">
    <label>分组结构</label>
    <select id="topology">
      <option value="global">全局 — 单一代理池，无区域分组</option>
      <option value="regional" selected>分区 — 各地区独立测速（推荐）</option>
      <option value="advanced">高级 — 分区 + 负载均衡</option>
    </select>
  </div>

  <div class="section" id="tier-section" style="display:none">
    <label>规则集格式（sing-box）</label>
    <select id="tier">
      <option value="1">Tier 1 — 经典合并（兼容性最佳）</option>
      <option value="2">Tier 2 — 分离格式（域名/IP 分离，性能最优）</option>
    </select>
  </div>

  <div class="section">
    <label>预设</label>
    <select id="preset">
      <option value="custom">自定义</option>
    </select>
  </div>

  <div class="section">
    <label>订阅链接（每行一个）</label>
    <textarea id="subs" placeholder="https://your-subscription-url/...&#10;https://backup-subscription-url/..."></textarea>
  </div>

  <div class="section" id="region-section">
    <label>排除节点关键词（正则，留空不排除）</label>
    <input id="region-excludes" type="text" placeholder="例: 5x|10x|0.5x" />
  </div>

  <div class="section">
    <label>功能开关</label>
    <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.4rem">
      <label class="cat-item"><input type="checkbox" id="feat-ads" checked> 广告拦截</label>
      <label class="cat-item"><input type="checkbox" id="feat-tracking"> 追踪拦截</label>
      <label class="cat-item"><input type="checkbox" id="feat-quic"> 屏蔽 QUIC</label>
      <label class="cat-item" id="feat-lb-wrap"><input type="checkbox" id="feat-lb"> 负载均衡（高级拓扑）</label>
    </div>
  </div>

  <div class="section" id="cat-section">
    <label>规则集 <span id="cat-count" style="color:#8b949e"></span></label>
    <div class="categories-grid" id="cat-grid"></div>
  </div>

  <div style="margin-top:1.5rem">
    <button class="btn" id="generate">生成配置</button>
    <button class="btn btn-secondary" id="copy">复制</button>
    <button class="btn btn-secondary" id="download">下载 .yaml</button>
  </div>

  <div id="output" class="output-block" style="display:none"></div>
`

let presets = {}
let catalog = null
let selectedGroups = new Set()

async function init() {
  const [catalogResult, presetsResult] = await Promise.allSettled([loadCatalog(), loadPresets()])
  catalog  = catalogResult.status  === 'fulfilled' ? catalogResult.value  : { items: {} }
  presets  = presetsResult.status  === 'fulfilled' ? presetsResult.value  : {}

  // Populate preset selector
  const presetEl = document.getElementById('preset')
  for (const [name, data] of Object.entries(presets)) {
    const opt = document.createElement('option')
    opt.value = name
    opt.textContent = `${name} — ${data.description || ''}`
    presetEl.appendChild(opt)
  }

  // Default to 'full' if available
  if (presets.full) {
    presetEl.value = 'full'
    applyPreset('full')
  }

  populateCatalogGrid(catalog)
}

function applyPreset(name) {
  const data = presets[name]
  if (!data) return
  selectedGroups = new Set(data.groups || [])

  // Sync topology and features from preset
  if (data.topology) document.getElementById('topology').value = data.topology
  if (data.features) {
    document.getElementById('feat-ads').checked      = !!data.features.ads_block
    document.getElementById('feat-tracking').checked = !!data.features.tracking_block
    document.getElementById('feat-quic').checked     = !!data.features.quic_block
    document.getElementById('feat-lb').checked       = !!data.features.load_balance
  }

  // Sync checkboxes
  document.querySelectorAll('#cat-grid input[type="checkbox"]').forEach(cb => {
    cb.checked = selectedGroups.has(cb.value)
  })
  updateCatCount()
}

function populateCatalogGrid(catalog) {
  const grid = document.getElementById('cat-grid')
  grid.innerHTML = ''
  for (const group of getGroups(catalog)) {
    const action = group.defaultAction === 'REJECT' ? 'block'
                 : group.defaultAction === 'DIRECT' ? 'direct' : 'proxy'
    const item = document.createElement('label')
    item.className = 'cat-item'
    item.innerHTML = `
      <input type="checkbox" value="${group.id}" ${selectedGroups.has(group.id) ? 'checked' : ''}>
      <span>${group.id}<span class="tag ${action}">${action}</span></span>
    `
    item.querySelector('input').addEventListener('change', e => {
      if (e.target.checked) selectedGroups.add(group.id)
      else selectedGroups.delete(group.id)
      updateCatCount()
    })
    grid.appendChild(item)
  }
  updateCatCount()
}

function updateCatCount() {
  document.getElementById('cat-count').textContent = `(${selectedGroups.size} 已选)`
}

// ── event listeners ───────────────────────────────────────────────────────────

document.getElementById('kernel').addEventListener('change', e => {
  const isSingbox  = e.target.value === 'singbox'
  document.getElementById('topology-section').style.display = isSingbox ? 'none' : ''
  document.getElementById('tier-section').style.display     = isSingbox ? '' : 'none'
  document.getElementById('region-section').style.display   = isSingbox ? 'none' : ''
})

document.getElementById('topology').addEventListener('change', e => {
  const showLB = e.target.value === 'advanced'
  document.getElementById('feat-lb-wrap').style.opacity = showLB ? '1' : '0.4'
})

document.getElementById('preset').addEventListener('change', e => {
  if (e.target.value !== 'custom') applyPreset(e.target.value)
})

document.getElementById('generate').addEventListener('click', () => {
  const kernel   = document.getElementById('kernel').value
  const topology = document.getElementById('topology').value
  const tier     = parseInt(document.getElementById('tier').value, 10)
  const preset   = document.getElementById('preset').value
  const groupIds = preset === 'custom' ? [...selectedGroups] : [...(new Set(presets[preset]?.groups || []))]
  const subs     = document.getElementById('subs').value.trim().split('\n').filter(Boolean)
  const regionExcludes = document.getElementById('region-excludes').value.trim()
  const features = {
    ads_block:       document.getElementById('feat-ads').checked,
    tracking_block:  document.getElementById('feat-tracking').checked,
    quic_block:      document.getElementById('feat-quic').checked,
    load_balance:    document.getElementById('feat-lb').checked,
  }

  let output
  if (kernel === 'singbox') {
    output = generateSingbox(groupIds, subs, tier)
  } else {
    const target = kernel  // 'mihomo' or 'mihomo-smart'
    output = buildFullProfile(subs, groupIds, catalog || { items: {} }, {
      topology, target, features, regionExcludes,
    })
  }

  const el = document.getElementById('output')
  el.textContent = output
  el.style.display = 'block'
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
})

document.getElementById('copy').addEventListener('click', () => {
  const text = document.getElementById('output').textContent
  if (text) navigator.clipboard.writeText(text).then(() => alert('已复制到剪贴板'))
})

document.getElementById('download').addEventListener('click', () => {
  const text = document.getElementById('output').textContent
  if (!text) return
  const preset = document.getElementById('preset').value
  const kernel = document.getElementById('kernel').value
  const ext    = kernel === 'singbox' ? 'json' : 'yaml'
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
  a.download = `${preset}-${kernel}.${ext}`
  a.click()
})

// ── sing-box output (fragment only) ──────────────────────────────────────────

function generateSingbox(groupIds, subs, tier) {
  const { ruleSets, routeRules } = buildSingboxRuleSets(groupIds, catalog || { items: {} }, { tier })
  const outbounds = [
    { tag: 'proxy',  type: 'selector', outbounds: ['auto', 'direct'] },
    { tag: 'auto',   type: 'urltest',  outbounds: ['direct'], url: 'https://cp.cloudflare.com', interval: '5m' },
    { tag: 'direct', type: 'direct' },
    { tag: 'block',  type: 'block' },
    { tag: 'dns-out',type: 'dns' },
  ]
  const config = {
    '$comment': `hajimihomo profile builder — sing-box fragment — tier ${tier}`,
    outbounds,
    route: {
      rule_set: ruleSets,
      rules: [
        { protocol: 'dns', outbound: 'dns-out' },
        ...routeRules,
        { geoip: 'cn', outbound: 'direct' },
      ],
      final: 'proxy',
      auto_detect_interface: true,
    },
  }
  return JSON.stringify(config, null, 2)
}

init()
