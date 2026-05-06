# Vendor Coverage Report

## Corpus Sizes

| Corpus | Files | Rules |
|---|---|---|
| gfwlist | 1 | 3,863 |
| loyalsoldier-gfw | 1 | 4,201 |
| loyalsoldier-direct | 1 | 114,728 |
| loyalsoldier-google-cn | 1 | 0 |
| dustinwin-cn | 1 | 114,807 |
| dustinwin-apple-cn | 1 | 243 |
| dustinwin-microsoft-cn | 1 | 168 |
| dustinwin-google-cn | 1 | 153 |
| 666os-release | 40 | 187,751 |
| our-china | 1 | 116,906 |
| our-advertising | 2 | 254,998 |

## Coverage Matrix

_% of row corpus's rules subsumed by column corpus_

| Corpus \ Covered by | gfwlist | loyalsoldier-gfw | loyalsoldier-direct | loyalsoldier-google-cn | dustinwin-cn | dustinwin-apple-cn | dustinwin-microsoft-cn | dustinwin-google-cn | 666os-release | our-china | our-advertising |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gfwlist |  —  | 100.0% | 0.5% | 0.0% | 0.4% | 0.0% | 0.0% | 0.1% | 93.7% | 0.8% | 1.1% |
| loyalsoldier-gfw | 91.9% |  —  | 0.5% | 0.0% | 0.4% | 0.0% | 0.0% | 0.1% | 93.0% | 0.7% | 1.0% |
| loyalsoldier-direct | 0.0% | 0.0% |  —  | 0.0% | 99.9% | 0.0% | 0.0% | 0.0% | 98.0% | 100.0% | 0.9% |
| loyalsoldier-google-cn | N/A | N/A | N/A |  —  | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| dustinwin-cn | 0.0% | 0.0% | 99.9% | 0.0% |  —  | 0.0% | 0.0% | 0.0% | 98.0% | 99.9% | 0.9% |
| dustinwin-apple-cn | 0.0% | 0.0% | 0.8% | 0.0% | 25.1% |  —  | 0.0% | 0.0% | 100.0% | 74.5% | 0.4% |
| dustinwin-microsoft-cn | 0.0% | 0.0% | 33.9% | 0.0% | 85.1% | 0.0% |  —  | 0.0% | 100.0% | 42.3% | 0.0% |
| dustinwin-google-cn | 51.0% | 51.6% | 2.0% | 0.0% | 5.2% | 0.0% | 0.0% |  —  | 100.0% | 95.4% | 24.2% |
| 666os-release | 2.4% | 2.6% | 60.2% | 0.0% | 60.5% | 0.2% | 0.1% | 0.1% |  —  | 61.5% | 0.7% |
| our-china | 0.1% | 0.1% | 98.1% | 0.0% | 98.0% | 0.2% | 0.0% | 0.1% | 98.0% |  —  | 0.9% |
| our-advertising | 0.6% | 0.6% | 3.0% | 0.0% | 6.1% | 0.0% | 0.0% | 0.0% | 15.4% | 3.1% |  —  |

## Novel Rules (not subsumed by any other corpus)

### gfwlist: 1 novel rules

- `DOMAIN-SUFFIX,xn--p8j9a0d9c9a.xn`

### loyalsoldier-gfw: 54 novel rules (showing first 5)

- `DOMAIN-SUFFIX,4sqi.net`
- `DOMAIN-SUFFIX,akamaihd.net`
- `DOMAIN-SUFFIX,blogspot.ae`
- `DOMAIN-SUFFIX,blogspot.al`
- `DOMAIN-SUFFIX,blogspot.am`

### loyalsoldier-direct: 0 novel rules


### loyalsoldier-google-cn: 0 novel rules


### dustinwin-cn: 19 novel rules (showing first 5)

- `DOMAIN-SUFFIX,123cha.com`
- `DOMAIN-SUFFIX,95081.com`
- `DOMAIN-SUFFIX,airasia.com`
- `DOMAIN-SUFFIX,alipay`
- `DOMAIN-SUFFIX,baidu`

### dustinwin-apple-cn: 0 novel rules


### dustinwin-microsoft-cn: 0 novel rules


### dustinwin-google-cn: 0 novel rules


### 666os-release: 66,472 novel rules (showing first 5)

- `DOMAIN-SUFFIX,agentclientprotocol.com`
- `DOMAIN-SUFFIX,ai.com`
- `DOMAIN-SUFFIX,aiproxy.io`
- `DOMAIN-SUFFIX,algolia.net`
- `DOMAIN-SUFFIX,antigravity-unleash.goog`

### our-china: 75 novel rules (showing first 5)

- `DOMAIN-SUFFIX,icbc.com.qa`
- `DOMAIN-SUFFIX,ipstatp.com`
- `DOMAIN-SUFFIX,digicert.com`
- `DOMAIN-SUFFIX,babymoment.net`
- `DOMAIN-SUFFIX,icbc.com.vn`

### our-advertising: 211,848 novel rules (showing first 5)

- `DOMAIN-SUFFIX,gtm.caraccidentcounsel.com`
- `DOMAIN-SUFFIX,d3cxv97fi8q177.cloudfront.net`
- `DOMAIN-SUFFIX,xsyqbdylnfpo.world`
- `DOMAIN-SUFFIX,vntupsfjqlsnb.online`
- `DOMAIN-SUFFIX,ei-api.testlb-gwy.easyjet.com.edgekey.net.easyjet.com`

## 666OS Files Not Referenced in categories.yaml

- `AI.txt` (4 rules)
- `Advertising.txt` (5 rules)
- `Apple.txt` (262 rules)
- `AppleCN.txt` (4 rules)
- `Bybit.txt` (2 rules)
- `China.txt` (19,782 rules)
- `Claude.txt` (1 rules)
- `Cloudflare.txt` (916 rules)
- `Crypto.txt` (7 rules)
- `Direct.txt` (15 rules)
- `Disney.txt` (4 rules)
- `Download.txt` (44 rules)
- `Emby.txt` (9 rules)
- `Facebook.txt` (108 rules)
- `Games.txt` (97 rules)
- `Gemini.txt` (3 rules)
- `GitHub.txt` (2 rules)
- `Google.txt` (5,959 rules)
- `HBO.txt` (0 rules)
- `Instagram.txt` (0 rules)
- `LocationDKS.txt` (0 rules)
- `Microsoft.txt` (65 rules)
- `Netflix.txt` (79 rules)
- `NewsMedia.txt` (24 rules)
- `OneDrive.txt` (0 rules)
- `OpenAI.txt` (7 rules)
- `PayPal.txt` (1 rules)
- `Private.txt` (21 rules)
- `Proxy.txt` (14 rules)
- `SocialMedia.txt` (16 rules)
- `Speedtest.txt` (3,773 rules)
- `Spotify.txt` (11 rules)
- `Streaming.txt` (16 rules)
- `SystemOTA.txt` (65 rules)
- `Telegram.txt` (24 rules)
- `TikTok.txt` (5 rules)
- `Tracking.txt` (437 rules)
- `Twitter.txt` (0 rules)
- `XPTV.txt` (18 rules)
- `YouTube.txt` (1 rules)
