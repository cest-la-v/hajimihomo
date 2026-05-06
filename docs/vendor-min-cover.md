# Vendor Minimum-Cover Analysis

## Part 1: Globally-Unique Rules Per Repo

Rules not covered by ANY other vendor repo.

| Repo | Total Rules | Globally Unique | Unique% |
|---|---:|---:|---:|
| `Loyalsoldier/surge-rules` | 302,650 | 106,791 | 35% |
| `Loyalsoldier/clash-rules` | 209,642 | 11,309 | 5% |
| `geekdada/surge-list` | 178,368 | 1,446 | 1% |
| `ACL4SSR/ACL4SSR` | 98,139 | 28,509 | 29% |
| `LM-Firefly/Rules` | 73,967 | 38,481 | 52% |
| `NobyDa/ND-AD` | 43,371 | 16,766 | 39% |
| `666OS/rules` | 12,751 | 6,615 | 52% |
| `gaoyifan/china-operator-ip` | 12,343 | 6,678 | 54% |
| `sve1r/Rules-For-Quantumult-X` | 12,233 | 250 | 2% |
| `missuo/ASN-China` | 11,667 | 488 | 4% |
| `dler-io/Rules` | 10,733 | 4,137 | 39% |
| `mieqq/mieqq` | 10,192 | 619 | 6% |
| `NobyDa/Script` | 9,721 | 2 | 0% |
| `Hackl0us/GeoIP2-CN` | 7,055 | 564 | 8% |
| `misakaio/chnroutes2` | 3,910 | 240 | 6% |
| `scomper/surge-list` | 3,225 | 5 | 0% |
| `zqzess/rule_for_quantumultX` | 2,513 | 1,021 | 41% |
| `Loyalsoldier/geoip` | 1,131 | 1,060 | 94% |
| `QiuSimons/Netflix_IP` | 1,118 | 6 | 1% |
| `Hackl0us/SS-Rule-Snippet` | 1,009 | 6 | 1% |
| `limbopro/Adblock4limbo` | 487 | 72 | 15% |
| `an0na/R` | 174 | 0 | 0% |
| `GeQ1an/Rules` | 158 | 0 | 0% |
| `tengyuankoo/qx` | 105 | 100 | 95% |
| `VirgilClyne/GetSomeFries` | 60 | 22 | 37% |
| `Mazetsz/ACL4SSR` | 31 | 2 | 6% |
| `tkzc11/QX-Rules` | 17 | 0 | 0% |
| `luuanng/surge` | 13 | 0 | 0% |
| `StricklandF/Filter` | 7 | 7 | 100% |

## Part 2: Redundant Repo Deep-Dive

For the high-redundancy repos (previously flagged), how many of their
'uncovered by primary' rules are covered by ANY other repo?

### `geekdada/surge-list`

- Total rules: 178,368
- Globally unique (no other repo covers them): 1,446 (0.8%)

<details><summary>Sample globally-unique rules</summary>

```
DOMAIN-SUFFIX,www.adxserve.com
DOMAIN-SUFFIX,assets.anzuinfra.com
DOMAIN-SUFFIX,emqx.anzuinfra.com
DOMAIN-SUFFIX,events.anzuinfra.com
DOMAIN-SUFFIX,logic.anzuinfra.com
DOMAIN-SUFFIX,appleads-trk.com
DOMAIN-SUFFIX,metabet.api.areyouwatchingthis.com
DOMAIN-SUFFIX,metabet.static.areyouwatchingthis.com
DOMAIN-SUFFIX,metabet.static.api.areyouwatchingthis.com
DOMAIN-SUFFIX,server.bidstack.com
DOMAIN-SUFFIX,cdn.brid.tv
DOMAIN-SUFFIX,p.brid.tv
DOMAIN-SUFFIX,services.brid.tv
DOMAIN-SUFFIX,customer.cludo.com
DOMAIN-SUFFIX,sitegenesis.production.deckers.coremedia.cloud
DOMAIN-SUFFIX,assets.emarsys.net
DOMAIN-SUFFIX,app.getwoohoo.com
DOMAIN-SUFFIX,mdp-appconf-sg.heytapdl.com
DOMAIN-SUFFIX,inhousedsp.com
DOMAIN-SUFFIX,sentry.justwatch.com
DOMAIN-SUFFIX,koneomobiledsp.com
DOMAIN-SUFFIX,ads.memob.com
DOMAIN-SUFFIX,api-ad-callback.mobiuspace.net
DOMAIN-SUFFIX,assets.narvar.com
DOMAIN-SUFFIX,pub.pixels.ai
DOMAIN-SUFFIX,static.returngo.ai
DOMAIN-SUFFIX,shalltry.com
DOMAIN-SUFFIX,apitm.toolmatrix.plus
DOMAIN-SUFFIX,converti.se
DOMAIN-SUFFIX,static2.manualslib.com
... and 1416 more
```
</details>

### `Loyalsoldier/clash-rules`

- Total rules: 209,642
- Globally unique (no other repo covers them): 11,309 (5.4%)

<details><summary>Sample globally-unique rules</summary>

```
DOMAIN-SUFFIX,1password.drift.click
DOMAIN-SUFFIX,a4e8s8k3.map2.ssl.hwcdn.net
DOMAIN-SUFFIX,adobeereg.com
DOMAIN-SUFFIX,anime-rule34-world.b-cdn.net
DOMAIN-SUFFIX,bbs.boingboing.net
DOMAIN-SUFFIX,beck-online.beck.de
DOMAIN-SUFFIX,crl.versign.net
DOMAIN-SUFFIX,datarouter.apps.netherrealm.com
DOMAIN-SUFFIX,dell.my.site.com
DOMAIN-SUFFIX,deutschewelle.h-cdn.com
DOMAIN-SUFFIX,dl.begellhouse.com
DOMAIN-SUFFIX,edu.tinkoff.ru
DOMAIN-SUFFIX,education.tbank.ru
DOMAIN-SUFFIX,firstsearch.oclc.org
DOMAIN-SUFFIX,github-api.arkoselabs.com
DOMAIN-SUFFIX,google-ohttp-relay-safebrowsing.fastly-edge.com
DOMAIN-SUFFIX,holoxx.f5.si
DOMAIN-SUFFIX,hub.slarker.me
DOMAIN-SUFFIX,i.jeded.com
DOMAIN-SUFFIX,ingest.apple-studies.com
DOMAIN-SUFFIX,live-patreon-marketing.pantheonsite.io
DOMAIN-SUFFIX,medone-education.thieme.com
DOMAIN-SUFFIX,ntp-b.nist.gov
DOMAIN-SUFFIX,ntp-c.colorado.edu
DOMAIN-SUFFIX,ntp-d.nist.gov
DOMAIN-SUFFIX,ntp-wwv.nist.gov
DOMAIN-SUFFIX,ntp.time.nl
DOMAIN-SUFFIX,ntp0.ntp-servers.net
DOMAIN-SUFFIX,ntp1.ntp-servers.net
DOMAIN-SUFFIX,ntp1.time.nl
... and 11279 more
```
</details>

### `NobyDa/Script`

- Total rules: 9,721
- Globally unique (no other repo covers them): 2 (0.0%)

<details><summary>Sample globally-unique rules</summary>

```
DOMAIN-SUFFIX,mg.5pk
DOMAIN-SUFFIX,xiaoqiang
```
</details>

### `scomper/surge-list`

- Total rules: 3,225
- Globally unique (no other repo covers them): 5 (0.2%)

<details><summary>Sample globally-unique rules</summary>

```
DOMAIN-SUFFIX,yangniupiju.com
DOMAIN-SUFFIX,lionettrip.xyz
DOMAIN-SUFFIX,jingteinv.com
DOMAIN-SUFFIX,xn--io0a7i.com
DOMAIN-SUFFIX,loli.io
```
</details>

### `an0na/R`

- Total rules: 174
- Globally unique (no other repo covers them): 0 (0.0%)

✅ All rules covered by other repos — safe to drop.

### `misakaio/chnroutes2`

- Total rules: 3,910
- Globally unique (no other repo covers them): 240 (6.1%)

<details><summary>Sample globally-unique rules</summary>

```
IP-CIDR,2.56.255.0/24
IP-CIDR,2.58.242.0/24
IP-CIDR,2.59.151.0/24
IP-CIDR,5.181.219.0/24
IP-CIDR,14.241.232.0/21
IP-CIDR,14.255.16.0/24
IP-CIDR,14.255.238.0/24
IP-CIDR,23.247.128.0/24
IP-CIDR,23.247.130.0/24
IP-CIDR,31.40.214.0/24
IP-CIDR,42.83.128.0/23
IP-CIDR,42.244.0.0/16
IP-CIDR,42.245.192.0/18
IP-CIDR,42.246.0.0/15
IP-CIDR,43.227.64.0/21
IP-CIDR,43.229.50.0/24
IP-CIDR,43.229.184.0/24
IP-CIDR,43.241.50.0/23
IP-CIDR,43.249.0.0/23
IP-CIDR,43.249.2.0/24
IP-CIDR,43.254.152.0/21
IP-CIDR,43.254.228.0/24
IP-CIDR,43.254.232.0/21
IP-CIDR,45.12.88.0/24
IP-CIDR,45.12.90.0/24
IP-CIDR,45.61.200.0/23
IP-CIDR,45.61.226.0/24
IP-CIDR,45.67.223.0/24
IP-CIDR,45.81.34.0/24
IP-CIDR,45.123.117.0/24
... and 210 more
```
</details>

### `missuo/ASN-China`

- Total rules: 11,667
- Globally unique (no other repo covers them): 488 (4.2%)

<details><summary>Sample globally-unique rules</summary>

```
IP-CIDR,14.136.132.0/27
IP-CIDR,14.136.137.0/26
IP-CIDR,17.87.32.0/21
IP-CIDR,17.87.56.0/21
IP-CIDR,17.88.112.0/21
IP-CIDR,27.105.61.224/27
IP-CIDR,27.124.42.14/32
IP-CIDR,38.47.254.0/24
IP-CIDR,38.196.176.0/24
IP-CIDR,43.128.125.0/24
IP-CIDR,43.128.126.0/23
IP-CIDR,43.128.192.0/24
IP-CIDR,45.116.80.0/26
IP-CIDR,45.116.80.128/25
IP-CIDR,45.116.81.0/24
IP-CIDR,45.116.82.0/23
IP-CIDR,45.137.238.16/28
IP-CIDR,46.151.181.0/24
IP-CIDR,49.64.0.0/13
IP-CIDR,49.72.0.0/14
IP-CIDR,49.76.0.0/18
IP-CIDR,49.76.64.0/19
IP-CIDR,49.76.96.0/22
IP-CIDR,49.76.100.0/23
IP-CIDR,49.76.102.0/24
IP-CIDR,49.76.103.64/26
IP-CIDR,49.76.103.128/25
IP-CIDR,49.76.104.0/21
IP-CIDR,49.76.112.0/20
IP-CIDR,49.76.128.0/17
... and 458 more
```
</details>

### `QiuSimons/Netflix_IP`

- Total rules: 1,118
- Globally unique (no other repo covers them): 6 (0.5%)

<details><summary>Sample globally-unique rules</summary>

```
IP-CIDR,34.223.96.0/22
IP-CIDR,52.24.178.0/24
IP-CIDR,52.35.140.0/24
IP-CIDR,54.213.167.0/24
IP-CIDR,203.198.13.0/24
IP-CIDR,203.198.80.0/24
```
</details>

## Part 3: Greedy Minimum Set Cover

Target: 484,586 unique rules across all repos.

**26 repos** cover **484,586/484,586** rules (100.0%).

| # | Repo | Rules | Cumulative Coverage |
|---|---|---:|---:|
| 1 | `Loyalsoldier/surge-rules` | +302,650 | 62.5% |
| 2 | `LM-Firefly/Rules` | +58,213 | 74.5% |
| 3 | `ACL4SSR/ACL4SSR` | +36,276 | 82.0% |
| 4 | `NobyDa/ND-AD` | +28,390 | 87.8% |
| 5 | `Loyalsoldier/clash-rules` | +14,490 | 90.8% |
| 6 | `gaoyifan/china-operator-ip` | +9,016 | 92.7% |
| 7 | `geekdada/surge-list` | +8,566 | 94.4% |
| 8 | `666OS/rules` | +7,081 | 95.9% |
| 9 | `missuo/ASN-China` | +6,127 | 97.2% |
| 10 | `mieqq/mieqq` | +5,245 | 98.2% |
| 11 | `dler-io/Rules` | +4,352 | 99.1% |
| 12 | `zqzess/rule_for_quantumultX` | +1,477 | 99.4% |
| 13 | `Loyalsoldier/geoip` | +1,082 | 99.7% |
| 14 | `Hackl0us/GeoIP2-CN` | +584 | 99.8% |
| 15 | `limbopro/Adblock4limbo` | +326 | 99.9% |
| 16 | `sve1r/Rules-For-Quantumult-X` | +266 | 99.9% |
| 17 | `misakaio/chnroutes2` | +240 | 100.0% |
| 18 | `tengyuankoo/qx` | +102 | 100.0% |
| 19 | `VirgilClyne/GetSomeFries` | +55 | 100.0% |
| 20 | `Hackl0us/SS-Rule-Snippet` | +13 | 100.0% |
| 21 | `scomper/surge-list` | +10 | 100.0% |
| 22 | `NobyDa/Script` | +8 | 100.0% |
| 23 | `StricklandF/Filter` | +7 | 100.0% |
| 24 | `QiuSimons/Netflix_IP` | +6 | 100.0% |
| 25 | `Mazetsz/ACL4SSR` | +3 | 100.0% |
| 26 | `luuanng/surge` | +1 | 100.0% |

**Uncovered by any repo:** 0 rules
