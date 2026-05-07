# Vendor Preset Reference

Extracted from community mihomo configs and DustinWin SubConverter templates.
Use this as a reference when building or modifying the web profile builder.

Last updated: 2026-05-07

---

## Summary Table

| Config | Source | Groups | Rules | Topology | geox-url | REJECT pattern |
|--------|--------|--------|-------|----------|----------|----------------|
| 666OS/MihomoPro | vendor/666OS/YYDS | 52 | 40 | LB-hash + LB-rr + url-test × 7 | none (geodata-mode) | hardcoded REJECT |
| 666OS/OneSmartPro | vendor/666OS/YYDS | 31 | 36 | smart × 7 + 4 fallback quality tiers | none | hardcoded REJECT |
| 666OS/OneSmart | vendor/666OS/YYDS | 16 | 21 | smart × 7 | none | hardcoded REJECT |
| 666OS/OneTouch | vendor/666OS/YYDS | 15 | 23 | url-test × 7 + fallback | none | hardcoded REJECT |
| naseem/OneSmart | vendor/naseem499379 | 31 | 36 | smart × 7 + 4 fallback quality tiers | none | hardcoded REJECT |
| naseem/OneSmartLite | vendor/naseem499379 | 16 | 21 | smart × 7 | none | hardcoded REJECT |
| Merge.yaml (user) | vendor/Merge.yaml | 28 | 110 | url-test × 6 + LB | MetaCubeX lite | named select groups |

---

## 666OS Rule Sets (shared across all 4 configs)

Base URL: `https://github.com/666OS/rules/raw/release/mihomo/`

Domain rules (behavior: domain): `Advertising`, `Tracking`, `Private`, `Direct`, `XPTV`, `AppleCN`, `Download`, `AI`, `Speedtest`, `Twitter`, `Telegram`, `SocialMedia`, `NewsMedia`, `Games`, `Crypto`, `Emby`, `Netflix`, `YouTube`, `Streaming`, `Apple`, `Google`, `Microsoft`, `Facebook`, `LocationDKS`, `Proxy`, `China`

IP rules (behavior: ipcidr): `AdvertisingIP`, `TrackingIP`, `PrivateIP`, `XPTVIP`, `AIIP`, `TelegramIP`, `SocialMediaIP`, `EmbyIP`, `NetflixIP`, `StreamingIP`, `GoogleIP`, `FacebookIP`, `ProxyIP`, `ChinaIP`

**Note:** 666OS configs use `geodata-mode: false` and rely entirely on rule-set matching. No `geox-url` needed.

### fake-ip-filter (all 4 share same list)
```yaml
fake-ip-filter:
  - rule-set:Direct
  - rule-set:Private
  - rule-set:China
  - +.miwifi.com
  - +.docker.io
  - +.market.xiaomi.com
  - +.push.apple.com
```

---

## 666OS/MihomoPro

**52 proxy groups — full LB topology**

| Name | Type | Proxies |
|------|------|---------|
| 默认代理 | select | 故障转移, 香港策略, 狮城策略, 日本策略, 韩国策略, 美国策略, 台湾策略, 欧盟策略, 冷门自选, 全球手动, 直接连接 |
| 故障转移 | fallback | 香港策略, 狮城策略, 日本策略, 韩国策略, 美国策略, 台湾策略, 欧盟策略, 全球手动, 冷门自选, 直接连接 |
| 国外流量 | select | 默认代理, 故障转移, [all regional策略], 冷门自选, 全球手动, 直接连接 |
| 国内流量 | select | 直接连接, [all regional策略] |
| 兜底流量 | select | 默认代理, [all regional策略] |
| 直接连接 | select | DIRECT |
| 网络测试 | select | 默认代理, [all regional策略] |
| 抖快书定位 | select | 直接连接, [all regional策略] |
| Emby服 | select | 默认代理, [all regional策略] |
| 油管视频 | select | 默认代理, [all regional策略] |
| 奈飞视频 | select | 默认代理, [all regional策略] |
| 国际媒体 | select | 默认代理, [all regional策略] |
| 新闻媒体 | select | 美国策略, 默认代理, [other regional策略] |
| 电报消息 | select | 默认代理, [all regional策略] |
| 推特社交 | select | 默认代理, [all regional策略] |
| 社交平台 | select | 默认代理, [all regional策略] |
| 人工智能 | select | 美国策略, 默认代理, [other regional策略] |
| 货币平台 | select | 狮城策略, 默认代理, [other regional策略] |
| 游戏平台 | select | 默认代理, [all regional策略] |
| 微软服务 | select | 默认代理, [all regional策略] |
| 谷歌服务 | select | 默认代理, [all regional策略] |
| 苹果服务 | select | 默认代理, [all regional策略] |
| 香港策略 | select | 香港自动, 香港均衡-散列, 香港均衡-轮询 |
| 台湾策略 | select | 台湾自动, 台湾均衡-散列, 台湾均衡-轮询 |
| 狮城策略 | select | 狮城自动, 狮城均衡-散列, 狮城均衡-轮询 |
| 日本策略 | select | 日本自动, 日本均衡-散列, 日本均衡-轮询 |
| 韩国策略 | select | 韩国自动, 韩国均衡-散列, 韩国均衡-轮询 |
| 美国策略 | select | 美国自动, 美国均衡-散列, 美国均衡-轮询 |
| 欧盟策略 | select | 欧盟自动, 欧盟均衡-散列, 欧盟均衡-轮询 |
| 冷门自选 | select | include-all (no filter) |
| 全球手动 | select | include-all (no filter) |
| 香港自动 | url-test | include-all, filter: HK regex |
| 台湾自动 | url-test | include-all, filter: TW regex |
| 狮城自动 | url-test | include-all, filter: SG regex |
| 日本自动 | url-test | include-all, filter: JP regex |
| 韩国自动 | url-test | include-all, filter: KR regex |
| 美国自动 | url-test | include-all, filter: US regex |
| 欧盟自动 | url-test | include-all, filter: EU regex |
| 香港均衡-散列 | load-balance (consistent-hashing) | include-all, filter: HK |
| 台湾均衡-散列 | load-balance | include-all, filter: TW |
| 狮城均衡-散列 | load-balance | include-all, filter: SG |
| 日本均衡-散列 | load-balance | include-all, filter: JP |
| 韩国均衡-散列 | load-balance | include-all, filter: KR |
| 美国均衡-散列 | load-balance | include-all, filter: US |
| 欧盟均衡-散列 | load-balance | include-all, filter: EU |
| 香港均衡-轮询 | load-balance (round-robin) | include-all, filter: HK |
| 台湾均衡-轮询 | load-balance | include-all, filter: TW |
| 狮城均衡-轮询 | load-balance | include-all, filter: SG |
| 日本均衡-轮询 | load-balance | include-all, filter: JP |
| 韩国均衡-轮询 | load-balance | include-all, filter: KR |
| 美国均衡-轮询 | load-balance | include-all, filter: US |
| 欧盟均衡-轮询 | load-balance | include-all, filter: EU |

**40 rules (in order):**
```
RULE-SET,Tracking,REJECT
RULE-SET,Advertising,REJECT
AND,((DST-PORT,443),(NETWORK,UDP),(NOT,((GEOIP,CN)))),REJECT
RULE-SET,LocationDKS,抖快书定位
RULE-SET,Private,直接连接
RULE-SET,Direct,直接连接
RULE-SET,XPTV,直接连接
RULE-SET,Download,直接连接
RULE-SET,AppleCN,直接连接
RULE-SET,AI,人工智能
DOMAIN-KEYWORD,speedtest,网络测试
RULE-SET,Speedtest,网络测试
RULE-SET,Twitter,推特社交
RULE-SET,Telegram,电报消息
RULE-SET,SocialMedia,社交平台
RULE-SET,NewsMedia,新闻媒体
RULE-SET,Games,游戏平台
RULE-SET,Crypto,货币平台
RULE-SET,Emby,Emby服
RULE-SET,Netflix,奈飞视频
RULE-SET,YouTube,油管视频
RULE-SET,Streaming,国际媒体
RULE-SET,Apple,苹果服务
RULE-SET,Google,谷歌服务
RULE-SET,Microsoft,微软服务
RULE-SET,Proxy,国外流量
RULE-SET,China,国内流量
RULE-SET,AdvertisingIP,REJECT,no-resolve
RULE-SET,PrivateIP,直接连接,no-resolve
RULE-SET,XPTVIP,直接连接,no-resolve
RULE-SET,AIIP,人工智能,no-resolve
RULE-SET,TelegramIP,电报消息,no-resolve
RULE-SET,SocialMediaIP,社交平台,no-resolve
RULE-SET,EmbyIP,Emby服,no-resolve
RULE-SET,NetflixIP,奈飞视频,no-resolve
RULE-SET,StreamingIP,国际媒体,no-resolve
RULE-SET,GoogleIP,谷歌服务,no-resolve
RULE-SET,ProxyIP,国外流量,no-resolve
RULE-SET,ChinaIP,国内流量
MATCH,兜底流量
```

---

## 666OS/OneSmartPro (= naseem/OneSmart)

**31 proxy groups — smart topology + 4 quality-tier fallback chains**

The "quality tier" concept: service groups pick from 4 fallback chains by preference:
- `高质量线路` (high quality) → US → HK → TW → JP → SG → KR → EU
- `低延迟线路` (low latency) → HK → TW → JP → SG → KR → US → EU
- `大带宽线路` (high bandwidth) → SG → HK → TW → JP → KR → US → EU
- `低倍率线路` (low multiplier) → JP → HK → TW → SG → KR → US → EU

| Name | Type | Default first choice |
|------|------|---------------------|
| 一键智能 | select | 高质量线路 |
| 网络测试 | select | 一键智能 |
| 人工智能 | select | 高质量线路 |
| 电报消息 | select | 大带宽线路 |
| 社交平台 | select | 低倍率线路 |
| 游戏平台 | select | 低延迟线路 |
| 货币平台 | select | 高质量线路 |
| Emby服 | select | 大带宽线路 |
| 国际媒体 | select | 大带宽线路 |
| 新闻媒体 | select | 高质量线路 |
| 苹果服务 | select | 高质量线路 |
| 谷歌服务 | select | 高质量线路 |
| 微软服务 | select | 高质量线路 |
| 脸书服务 | select | 高质量线路 |
| 国外流量 | select | 高质量线路 |
| 国内流量 | select | 直接连接 |
| 兜底流量 | select | 高质量线路 |
| 手动选择 | select | include-all (filtered) |
| 直接连接 | select | DIRECT |
| 高质量线路 | fallback | US → HK → TW → JP → SG → KR → EU |
| 低延迟线路 | fallback | HK → TW → JP → SG → KR → US → EU |
| 大带宽线路 | fallback | SG → HK → TW → JP → KR → US → EU |
| 低倍率线路 | fallback | JP → HK → TW → SG → KR → US → EU |
| 香港智能 | smart | include-all, filter: HK |
| 台湾智能 | smart | include-all, filter: TW |
| 日本智能 | smart | include-all, filter: JP |
| 狮城智能 | smart | include-all, filter: SG |
| 韩国智能 | smart | include-all, filter: KR |
| 美国智能 | smart | include-all, filter: US |
| 欧洲智能 | smart | include-all, filter: EU |
| 中转服务 | load-balance | include-all (relay nodes) |

**36 rules:** (same as MihomoPro minus LocationDKS/Download/Twitter split, plus Facebook)
```
RULE-SET,Tracking,REJECT
RULE-SET,Advertising,REJECT
AND,((DST-PORT,443),(NETWORK,UDP),(NOT,((GEOIP,CN)))),REJECT
RULE-SET,Private,直接连接
RULE-SET,Direct,直接连接
RULE-SET,XPTV,直接连接
RULE-SET,AppleCN,直接连接
RULE-SET,AI,人工智能
DOMAIN-KEYWORD,speedtest,网络测试
RULE-SET,Speedtest,网络测试
RULE-SET,Telegram,电报消息
RULE-SET,SocialMedia,社交平台
RULE-SET,NewsMedia,新闻媒体
RULE-SET,Games,游戏平台
RULE-SET,Crypto,货币平台
RULE-SET,Emby,Emby服
RULE-SET,Streaming,国际媒体
RULE-SET,Apple,苹果服务
RULE-SET,Google,谷歌服务
RULE-SET,Microsoft,微软服务
RULE-SET,Facebook,脸书服务
RULE-SET,Proxy,国外流量
RULE-SET,China,国内流量
RULE-SET,AdvertisingIP,REJECT,no-resolve
RULE-SET,PrivateIP,直接连接,no-resolve
RULE-SET,XPTVIP,直接连接,no-resolve
RULE-SET,AIIP,人工智能,no-resolve
RULE-SET,TelegramIP,电报消息,no-resolve
RULE-SET,SocialMediaIP,社交平台,no-resolve
RULE-SET,EmbyIP,Emby服,no-resolve
RULE-SET,StreamingIP,国际媒体,no-resolve
RULE-SET,GoogleIP,谷歌服务,no-resolve
RULE-SET,FacebookIP,脸书服务,no-resolve
RULE-SET,ProxyIP,国外流量,no-resolve
RULE-SET,ChinaIP,国内流量
MATCH,兜底流量
```

---

## 666OS/OneSmart (= naseem/OneSmartLite)

**16 proxy groups — smart topology, minimal service groups**

| Name | Type | Proxies |
|------|------|---------|
| 一键智能 | select | 香港智能, 台湾智能, 日本智能, 狮城智能, 韩国智能, 美国智能, 欧洲智能, 手动选择, 直接连接 |
| 人工智能 | select | 一键智能, [all regional智能] |
| 社交平台 | select | 一键智能, [all regional智能] |
| 国际媒体 | select | 一键智能, [all regional智能] |
| 国外流量 | select | 一键智能, [all regional智能] |
| 国内流量 | select | 直接连接, 一键智能, [all regional智能] |
| 兜底流量 | select | 一键智能, [all regional智能] |
| 手动选择 | select | include-all (filtered) |
| 直接连接 | select | DIRECT |
| 香港智能 | smart | include-all, filter: HK |
| 台湾智能 | smart | include-all, filter: TW |
| 日本智能 | smart | include-all, filter: JP |
| 狮城智能 | smart | include-all, filter: SG |
| 韩国智能 | smart | include-all, filter: KR |
| 美国智能 | smart | include-all, filter: US |
| 欧洲智能 | smart | include-all, filter: EU |

**21 rules:**
```
AND,((DST-PORT,443),(NETWORK,UDP),(NOT,((GEOIP,CN)))),REJECT
RULE-SET,Private,直接连接
RULE-SET,Direct,直接连接
RULE-SET,XPTV,直接连接
RULE-SET,AI,人工智能
RULE-SET,Telegram,社交平台
RULE-SET,SocialMedia,社交平台
RULE-SET,Emby,国际媒体
RULE-SET,Streaming,国际媒体
RULE-SET,Proxy,国外流量
RULE-SET,China,国内流量
RULE-SET,PrivateIP,直接连接,no-resolve
RULE-SET,XPTVIP,直接连接,no-resolve
RULE-SET,AIIP,人工智能,no-resolve
RULE-SET,TelegramIP,社交平台,no-resolve
RULE-SET,SocialMediaIP,社交平台,no-resolve
RULE-SET,EmbyIP,国际媒体,no-resolve
RULE-SET,StreamingIP,国际媒体,no-resolve
RULE-SET,ProxyIP,国外流量,no-resolve
RULE-SET,ChinaIP,国内流量
MATCH,兜底流量
```

---

## 666OS/OneTouch

**15 proxy groups — url-test topology (no smart), minimal service groups**

| Name | Type | Proxies |
|------|------|---------|
| 一键连 | select | 故障转移, 香港自动, 台湾自动, 日本自动, 狮城自动, 韩国自动, 美国自动, 欧洲自动, 手动选择, 直接连接 |
| 故障转移 | fallback | 香港自动, 台湾自动, 狮城自动, 日本自动, 韩国自动, 美国自动, 手动选择 |
| 人工智能 | select | 美国自动, 一键连, [other regional自动] |
| 社交平台 | select | 一键连, [all regional自动] |
| 国际媒体 | select | 一键连, [all regional自动] |
| 国内流量 | select | 直接连接, 一键连, [all regional自动] |
| 手动选择 | select | include-all (filtered) |
| 直接连接 | select | DIRECT |
| 香港自动 | url-test | include-all, filter: HK |
| 台湾自动 | url-test | include-all, filter: TW |
| 日本自动 | url-test | include-all, filter: JP |
| 狮城自动 | url-test | include-all, filter: SG |
| 韩国自动 | url-test | include-all, filter: KR |
| 美国自动 | url-test | include-all, filter: US |
| 欧洲自动 | url-test | include-all, filter: EU |

**23 rules:**
```
AND,((DST-PORT,443),(NETWORK,UDP),(NOT,((GEOIP,CN)))),REJECT
RULE-SET,Private,直接连接
RULE-SET,Direct,直接连接
RULE-SET,AppleCN,直接连接
RULE-SET,Download,直接连接
RULE-SET,XPTV,直接连接
RULE-SET,AI,人工智能
RULE-SET,Telegram,社交平台
RULE-SET,SocialMedia,社交平台
RULE-SET,YouTube,国际媒体
RULE-SET,Spotify,国际媒体
RULE-SET,Netflix,国际媒体
RULE-SET,Disney,国际媒体
RULE-SET,HBO,国际媒体
RULE-SET,Proxy,一键连
RULE-SET,China,国内流量
RULE-SET,PrivateIP,直接连接,no-resolve
RULE-SET,TelegramIP,社交平台,no-resolve
RULE-SET,SocialMediaIP,社交平台,no-resolve
RULE-SET,NetflixIP,国际媒体,no-resolve
RULE-SET,ProxyIP,一键连,no-resolve
RULE-SET,ChinaIP,国内流量
MATCH,一键连
```

---

## Merge.yaml (user's customized config)

**28 proxy groups — url-test × 6 regions + LB for relay nodes**

### geox-url (MetaCubeX lite)
```yaml
geox-url:
  geosite: https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geosite.dat
  geoip:   https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip-lite.dat
  mmdb:    https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country-lite.mmdb
  asn:     https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/GeoLite2-ASN.mmdb
```

### fake-ip-filter
```yaml
fake-ip-filter:
  - geosite:private
  - geosite:connectivity-check
  - geosite:tracker
  - rule-set:fakeip-filter
```

### REJECT pattern (key lesson)
Uses **named select groups** instead of hardcoded REJECT:
```yaml
- name: '🆎 AdBlock'
  type: select
  proxies: [REJECT, DIRECT]
- name: '🍃 应用净化'
  type: select
  proxies: [REJECT, DIRECT]
```
Rules route to these groups: `RULE-SET,AdvertisingLite_Domain,🆎 AdBlock`
This allows dashboard-level toggle between REJECT and DIRECT without editing YAML.

### Proxy groups

| Name | Type | First proxies |
|------|------|--------------|
| 通知公告 | select | include-all, filter: announcement keywords |
| Proxy | select | Auto-Fast, Auto-Edge, 香港节点, 台湾节点, 美国节点, 日本节点, 韩国节点, 狮城节点 |
| Auto-Fast | url-test | 香港节点, 台湾节点, 日本节点, 狮城节点 |
| Auto-Edge | load-balance | include-all, filter: CDN/relay keywords |
| 香港节点 | url-test | include-all, filter: HK (excludes X5/X10 nodes) |
| 台湾节点 | url-test | include-all, filter: TW |
| 美国节点 | url-test | include-all, filter: US |
| 日本节点 | url-test | include-all, filter: JP |
| 韩国节点 | url-test | include-all, filter: KR |
| 狮城节点 | url-test | include-all, filter: SG |
| AI | select | 美国节点, 台湾节点 (dedicated IPs filter) |
| Bing | select | DIRECT, Proxy, Auto-Fast, Auto-Edge, [regional] |
| GitHub | select | Proxy, DIRECT, [regional] |
| Steam | select | Proxy, DIRECT, [regional] |
| Epic | select | Proxy, DIRECT, [regional] |
| Bahamut | select | 台湾节点 only |
| Netflix | select | Auto-Edge, 美国节点, 台湾节点 (NF unlock filter) |
| TikTok | select | 美国节点 only |
| 谷歌服务 | select | 美国节点 (default) |
| 苹果服务 | select | DIRECT, Proxy, [regional] |
| 微软服务 | select | DIRECT, Proxy, [regional] |
| Game | select | DIRECT, Proxy, [regional] |
| Streaming | select | Proxy, DIRECT, [regional] |
| Social | select | Proxy, DIRECT, [regional] |
| Scholar | select | Proxy, DIRECT, [regional] |
| 🆎 AdBlock | select | REJECT, DIRECT |
| 🍃 应用净化 | select | REJECT, DIRECT |
| 🐟 漏网之鱼 | select | Proxy, DIRECT, [regional] |

### 110 rules (condensed)
```
# Dashboard domains → DIRECT
DOMAIN,clash.razord.top,DIRECT
DOMAIN,yacd.haishan.me,DIRECT
DOMAIN,board.zash.run.place,DIRECT

# Private/DNS infrastructure → DIRECT
RULE-SET,private,DIRECT
RULE-SET,privateip,DIRECT,no-resolve
RULE-SET,NTPService,DIRECT
# DNS server IPs hardcoded DIRECT (1.1.1.1, 8.8.8.8, 9.9.9.9, etc.)
IP-CIDR,1.1.1.1/32,DIRECT,no-resolve  # ... (20 IP-CIDR rules total)
RULE-SET,BlockHttpDNS,REJECT
RULE-SET,ChinaDNS,DIRECT
RULE-SET,DNS,DIRECT

# Manual overrides
DOMAIN-SUFFIX,settings-win.data.microsoft.com,DIRECT
DOMAIN,cdn.jsdelivr.net,Proxy
DOMAIN-SUFFIX,push.douban.com,REJECT

# Base direct/block
RULE-SET,Direct,DIRECT
RULE-SET,Custom_Direct,DIRECT,no-resolve
# Several manual DOMAIN/DOMAIN-SUFFIX exceptions (analytics, tracking SDKs → DIRECT)

# Ad blocking → named groups
RULE-SET,AdvertisingLite_Domain,🆎 AdBlock
RULE-SET,AdvertisingLite_No_Resolve,🆎 AdBlock
RULE-SET,Hijacking,🍃 应用净化

# Process overrides
RULE-SET,applications,DIRECT
PROCESS-NAME,小米互联服务,DIRECT
PROCESS-NAME,WeChat,DIRECT

# AI services
RULE-SET,Claude,AI
RULE-SET,Copilot,AI
RULE-SET,Gemini,AI
RULE-SET,OpenAI,AI
RULE-SET,ai,AI

# Tech services
RULE-SET,DigiCert,DIRECT
RULE-SET,IPLookup,Proxy
RULE-SET,networktest,Proxy
RULE-SET,Apple,苹果服务
RULE-SET,GoogleFCM,谷歌服务
RULE-SET,Google,谷歌服务
RULE-SET,Bing,Bing
RULE-SET,GitHub,GitHub
AND,((DOMAIN,github.com),(DST-PORT,22)),GitHub
RULE-SET,Microsoft,微软服务

# Social
RULE-SET,Facebook,Social
RULE-SET,Instagram,Social
RULE-SET,Telegram,Social
RULE-SET,Twitter,Social
RULE-SET,Whatsapp,Social

# Streaming
RULE-SET,Bahamut,Bahamut
RULE-SET,tiktok,TikTok
RULE-SET,netflix,Netflix
RULE-SET,ChinaMedia,DIRECT
RULE-SET,media,Streaming

# Gaming
DOMAIN-SUFFIX,steamcdn-a.akamaihd.net,DIRECT
RULE-SET,games-cn,DIRECT
RULE-SET,Epic,Epic
RULE-SET,Steam,Steam
RULE-SET,games,Game

# Catch-all proxy/direct
RULE-SET,ChinaMaxNoIP_Domain,DIRECT
RULE-SET,ChinaMaxNoIP_No_Resolve,DIRECT
RULE-SET,Proxy_Domain,Proxy
RULE-SET,Proxy_No_Resolve,Proxy

# GeoSite/GeoIP
GEOSITE,category-scholar-!cn,Scholar
GEOSITE,google-scholar,Scholar
GEOIP,private,DIRECT,no-resolve
GEOIP,telegram,Social
RULE-SET,telegramip,Social
RULE-SET,netflixip,Netflix
RULE-SET,mediaip,Streaming

# Process-level
PROCESS-PATH-REGEX,^/Applications/Antigravity.app/.*$,AI
GEOIP,jp,Proxy
GEOIP,cn,DIRECT
MATCH,🐟 漏网之鱼
```

---

## DustinWin SubConverter Templates

These are SubConverter `.ini` templates, not mihomo YAML. Group names are SubConverter proxy group names.
Base ruleset URL: `https://github.com/DustinWin/domain-list-custom/releases/download/domains/`

### Tier comparison (rule-sets per template)

| Template | Rule-sets | Ads | Tracker | MS/Apple/Google/Gaming | Netflix | YouTube | Media | AI | Telegram |
|----------|-----------|-----|---------|------------------------|---------|---------|-------|----|---------|
| Nano | 2 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Light | 6 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Blacklist | 11 | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Blacklist_NoAds | 10 | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Blacklist_BestCF | 6 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Lite | 15 | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Lite_NoAds | 14 | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Full | 21 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Full_NoAds | 20 | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### DustinWin_Full rule-sets (21 total, in order)
```
🎯 全球直连  ← private domains
🛑 广告域名  ← ads.list
📋 Trackerslist
🪟 微软服务  ← microsoft-cn.list
🍎 苹果服务  ← apple-cn.list
🇬 谷歌服务   ← google-cn.list
🎮 游戏服务  ← games-cn.list
🕹️ 游戏平台  ← games.list
🎥 奈飞视频  ← netflix.list
📹 油管视频  ← youtube.list
🌍 国外媒体  ← media.list
🤖 AI 平台   ← ai.list
📈 网络测试  ← networktest.list
🌎 国外域名  ← proxy.list (domain)
🇨🇳 国内域名 ← cn.list (domain)
🎯 全球直连  ← privateip.list (IP)
🀄️ 国内 IP   ← cnip.list (IP)
📲 电报消息  ← telegramip.list (IP)
🎥 奈飞视频  ← netflixip.list (IP)
🌍 国外媒体  ← mediaip.list (IP) — only in Full
🐟 漏网之鱼  ← FINAL (catch-all)
```

### DustinWin_Lite rule-sets (15 total)
```
🎯 全球直连, 🛑 广告域名, 📋 Trackerslist,
🪟 微软服务, 🍎 苹果服务, 🇬 谷歌服务, 🎮 游戏服务,
🤖 AI 平台, 📈 网络测试,
🌎 国外域名, 🇨🇳 国内域名,
🎯 全球直连 (IP), 🀄️ 国内 IP, 📲 电报消息 (IP),
🐟 漏网之鱼
```

### DustinWin_Blacklist rule-sets (11 total)
```
🎯 全球直连, 🛑 广告域名, 📋 Trackerslist,
🕹️ 游戏平台, 🤖 AI 平台, 📈 网络测试,
🌎 国外域名 (domain + IP),
🎯 全球直连 (IP),
📲 电报消息 (IP),
🐟 漏网之鱼
```
Note: Uses GFW proxy-list approach (proxy.list) rather than per-service MS/Apple/Google routing.

### DustinWin_Light rule-sets (6 total)
```
🎯 全球直连 (domains), 🌎 国外域名, 🇨🇳 国内域名,
🎯 全球直连 (IP), 🀄️ 国内 IP,
🐟 漏网之鱼
```
Bare minimum: CN direct + global proxy + CN IP. No per-service routing at all.

### DustinWin_Nano rule-sets (2 total)
```
🎯 全球直连 (private domains only),
🐟 漏网之鱼
```
Absolutely minimal: private direct, everything else proxied.

---

## Key Patterns (lessons for our profile builder)

### 1. REJECT pattern — use named select groups
All community configs that allow user control use named groups instead of hardcoded REJECT:
```yaml
# ✅ Correct — user can toggle in dashboard
- name: '🚫 广告拦截'
  type: select
  proxies: [REJECT, DIRECT, 默认代理]
rules:
  - RULE-SET,block-ads,🚫 广告拦截
  - RULE-SET,block-ads-ip,🚫 广告拦截,no-resolve

# ❌ Wrong — user cannot toggle
rules:
  - RULE-SET,block-ads,REJECT
```

### 2. QUIC blocking
All 666OS configs use this pattern (NOT just `DST-PORT,443,REJECT`):
```yaml
AND,((DST-PORT,443),(NETWORK,UDP),(NOT,((GEOIP,CN)))),REJECT
```
This only blocks QUIC for non-CN destinations, avoiding breaking domestic services.

### 3. Region filter regex (production-quality)
```
HK: ^(?=.*(?i)(港|🇭🇰|HK|Hong|HKG))(?!.*(排除关键词|X5|5x|X10|10x)).*$
TW: ^(?=.*(?i)(台|🇹🇼|TW|TWN|Taiwan|TPE|TSA|KHH))(?!.*(排除关键词)).*$
JP: ^(?=.*(?i)(日|🇯🇵|JP|Japan|NRT|HND|KIX|CTS|FUK))(?!.*(排除关键词)).*$
SG: ^(?=.*(?i)(坡|🇸🇬|SG|Sing|SIN|XSP))(?!.*(排除关键词)).*$
KR: ^(?=.*(?i)(韩|🇰🇷|韓|首尔|南朝鲜|KR|KOR|Korea|ICN))(?!.*(排除关键词)).*$
US: ^(?=.*(?i)(美|🇺🇸|US|USA|SJC|JFK|LAX|ORD|ATL|DFW|SFO|MIA|SEA|IAD))(?!.*(排除关键词)).*$
EU: ^(?=.*(?i)(奥|比|保|克罗地亚|塞|捷|丹|爱沙|芬|法|德|希|匈|爱|意|拉|立|卢|马|荷|波|葡|罗|斯洛文|斯洛伐|西|瑞典|英|🇩🇪|🇫🇷|🇬🇧|🇳🇱|🇸🇪|CDG|FRA|AMS|LHR|FCO|FRA|MUC)).*$
```

Exclusion filter (remove spam/announcement nodes):
```
^(?!.*(群|邀请|返利|循环|官网|客服|网站|网址|获取|订阅|流量|到期|机场|下次|版本|官址|备用|过期|已用|联系|邮箱|工单|贩卖|通知|倒卖|防止|国内|地址|频道|无法|说明|使用|提示|特别|访问|支持|教程|关注|更新|作者|加入|USE|USED|TOTAL|EXPIRE|EMAIL|Panel|Channel|Author))
```

### 4. fake-ip-filter best practices
666OS uses rule-set references (requires mihomo ≥ 1.18):
```yaml
fake-ip-filter:
  - rule-set:Direct    # CN direct domains
  - rule-set:Private   # private/LAN
  - rule-set:China     # all CN domains
  - +.miwifi.com
  - +.docker.io
  - +.market.xiaomi.com
  - +.push.apple.com
```
Merge.yaml uses geosite references:
```yaml
fake-ip-filter:
  - geosite:private
  - geosite:connectivity-check
  - geosite:tracker
  - rule-set:fakeip-filter  # custom list
```

### 5. Service group default first choice (from MihomoPro)
The first proxy in a service group's list is the default. Community conventions:
- AI → 美国 first (US has best AI access)
- Netflix → 美国 or dedicated streaming nodes first
- Telegram → 大带宽线路 or 狮城 first (high bandwidth for large files)
- Social → 低倍率线路 first (low cost for browsing)
- Gaming → 低延迟线路 or 香港 first (low latency)
- Finance/Crypto → 狮城 first (financial hub)
- Streaming/Media → 大带宽线路 or 狮城 first

### 6. Topology mapping to group types
| Topology | Regional groups | Service group choices |
|----------|----------------|----------------------|
| minimal | none (global 全部 only) | 默认代理, 直接连接 |
| standard | url-test × regions | regional + 默认代理 + 直接连接 |
| full | url-test + LB × regions | regional策略 (which selects url-test or LB) |
| mihomo-smart | smart × regions | regional智能 + quality fallback chains |

### 7. YAML anchor templates (from 666OS/OneSmartPro)
666OS configs use compact one-line YAML with anchors for clean, DRY definitions:
```yaml
# Group type templates
BaseFB:    &BaseFB    {type: fallback,      interval: 200, lazy: true, url: 'https://www.google.com/generate_204'}
BaseLB:    &BaseLB    {type: load-balance,  interval: 200, lazy: true, url: 'https://www.google.com/generate_204'}
BaseSmart: &BaseSmart {type: smart,         interval: 200, lazy: true, url: 'https://www.google.com/generate_204', hidden: true, uselightgbm: true}

# Region filter anchors
FilterHK: &FilterHK '^(?=.*(?i)(港|🇭🇰|HK|Hong|HKG))(?!.*(排除1|排除2|5x)).*$'
FilterTW: &FilterTW '^(?=.*(?i)(台|🇹🇼|TW|TWN|Taiwan|TPE|TSA|KHH))(?!.*(排除)).*$'
FilterJP: &FilterJP '^(?=.*(?i)(日|🇯🇵|JP|Japan|NRT|HND|KIX|CTS|FUK))(?!.*(排除)).*$'
FilterSG: &FilterSG '^(?=.*(?i)(坡|🇸🇬|SG|Sing|SIN|XSP))(?!.*(排除)).*$'
FilterKR: &FilterKR '^(?=.*(?i)(韩|🇰🇷|韓|首尔|南朝鲜|KR|KOR|Korea|ICN))(?!.*(排除)).*$'
FilterUS: &FilterUS '^(?=.*(?i)(美|🇺🇸|US|USA|SJC|JFK|LAX|ORD|ATL|DFW|SFO|MIA|SEA|IAD))(?!.*(排除)).*$'
FilterEU: &FilterEU '^(?=.*(?i)(奥|比|保|克罗地亚|塞|捷|丹|爱沙|芬|法|德|希|匈|爱|意|拉|立|卢|马|荷|波|葡|罗|西|瑞典|英|🇩🇪|🇫🇷|🇬🇧|🇳🇱|🇸🇪|CDG|FRA|AMS|LHR|MUC)).*$'

# Proxy provider template
BaseProvider: &BaseProvider
  type: http
  interval: 86400
  proxy: DIRECT
  health-check: {enable: true, url: 'https://www.google.com/generate_204', interval: 300}
  filter: '^(?!.*(群|邀请|返利|循环|官网|客服|网站|网址|获取|订阅|流量|到期|机场|下次|版本|官址|备用|过期|已用|联系|邮箱|工单|贩卖|通知|倒卖|防止|国内|地址|频道|无法|说明|使用|提示|特别|访问|支持|教程|关注|更新|作者|加入|USE|USED|TOTAL|EXPIRE|EMAIL|Panel|Channel|Author))'

# Usage in group definition:
- {name: 香港智能, <<: *BaseSmart, filter: *FilterHK, include-all: true, policy-priority: '优:2;中:1;备:0.5', icon: https://github.com/Koolson/Qure/raw/master/IconSet/Color/Hong_Kong.png}
```

`policy-priority` is a `smart` group feature (vernesong/mihomo fork only): weights named node tiers.
Format: `'优:2;中:1;备:0.5'` — nodes matching keyword `优` get weight 2, `中` get 1, `备` get 0.5.

### 8. Group icons (Koolson/Qure CDN)
```
Base: https://github.com/Koolson/Qure/raw/master/IconSet/Color/
Hong_Kong.png, Taiwan.png, Japan.png, Singapore.png, United_States.png,
Korea.png, European_Union.png, Round_Robin.png, Round_Robin_1.png,
Apple.png, Google.png, Microsoft.png, Telegram.png, Twitter.png,
Netflix.png, YouTube.png, Streaming.png, AI.png, Gaming.png,
Direct.png, Proxy.png, Available.png, Bypass.png
```
