# AGENTS.md

## Project Overview

**hajimihomo** is a mihomo/Clash Meta ruleset build system. It aggregates proxy routing rules from multiple upstream sources (primarily [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)), resolves them into clean rule sets, and publishes them to CDN branches for use in proxy clients.

Two deliverables:
1. **Rule sets** — built by `scripts/build.py`, published to `dist/` and CDN branches. Each group produces multiple output files per format tier (see [Source Structure](#source-structure)).
2. **Interactive profile builder** — a static web app (`web/`) deployed to GitHub Pages that lets users generate complete, standalone mihomo config files.

**Key technologies:** Python 3 · PyYAML · Bun · JavaScript (ES modules) · GitHub Actions · jsDelivr CDN

**Branch model:**
- `dev` — all source edits, PRs, CI builds
- `ruleset` (auto-managed) — published text rule sets (`dist/mihomo/*.yaml`, `dist/singbox/*.json`)
- `release` (auto-managed) — compiled binaries (`.mrs`, `.srs`)
- `gh-pages` (auto-managed) — profile builder web app

---

## Setup

### Python (rule builder)

```bash
pip install pyyaml   # system Python 3.12+, only dep needed
```

### Bun (web profile builder + CLI)

```bash
make web-install   # cd web && bun install
```

Requires [Bun](https://bun.sh) ≥ 1.x.

### Vendor repos

```bash
make vendor-sync   # clone/update all upstream repos referenced by repo: sources
```

Vendor repos are cloned into `vendor/` (gitignored). Required for source extraction and coverage analysis, but not for building (build fetches sources directly via HTTP).

---

## Source Structure

```
source/
  categories.yaml   # 664 leaf categories — each maps to upstream rule sources
  catalog.yaml      # 24 policy groups — semantic bundles of leaf categories
  overrides/        # local override lists (override: prefix = replace source entirely)
  hosts/
    polluted.yaml   # DNS-polluted domains for hosts block generation
    overrides.yaml  # manually pinned IPs (take priority over DoH results)

profiles/
  presets/          # 1-mini / 2-lite / 3-standard / 4-full preset definitions
  defaults/
    mihomo.yaml     # editable base config (core, DNS, sniffer, TUN) — imported by ProfileBuilder
    singbox.json    # sing-box base config (future wiring)
  user.yaml.example # copy to profiles/user.yaml and fill in subscriptions

scripts/
  build.py              # main rule-set builder
  validate.py           # source YAML validation
  extract_sources.py    # re-extracts sources from blackmatrix7 vendor
  build_hosts.py        # DoH cross-validation hosts block builder
  vendor_sync.py        # vendor repo cloner/updater
  stats.py              # build stats and diff report

web/
  src/
    ProfileBuilder.js   # core profile generation logic (runs in browser + CLI)
    main.js             # UI wiring
  cli.ts                # Bun CLI entry point → make profile
  hosts.ts              # DoH host resolution (used by CLI)
  index.html            # app shell
  build.ts              # Bun build script → web/dist/
  dev.ts                # Bun dev server (port 5173)
```

---

## Development Workflow

### Rule-set builder

```bash
make build                           # build atomics + all catalog groups (CI mode)
make build-groups                    # catalog groups only (skips 664 atomics)
make build-groups GROUPS=proxy/telegram,block/ads   # specific groups only
make build-dry                       # dry-run: validate graph, no file output
make validate                        # validate source/categories.yaml + catalog.yaml
```

Output lands in `dist/mihomo/` and `dist/singbox/`.

**Dist output format tiers** — for each catalog group, `build.py` emits:

| File | Behavior | Content | Used for |
|------|----------|---------|---------|
| `<slug>.yaml` | classical | All rule types | Tier 1: broadest compat, one file |
| `<slug>.domain.yaml` | domain | DOMAIN + DOMAIN-SUFFIX only | Tier 2 split |
| `<slug>.ip.yaml` | ipcidr | IP-CIDR (with no-resolve) | Tier 2 split |
| `<slug>.ip-resolve.yaml` | ipcidr | IP-CIDR (without no-resolve) | Tier 2: load LAST globally |
| `<slug>.residual.yaml` | classical | DOMAIN-KEYWORD, DOMAIN-REGEX, IP-ASN | Tier 2 split |
| `<slug>.process.yaml` | classical | PROCESS-NAME only | Tier 2 split |

Binary versions (`.mrs` for mihomo, `.srs` for sing-box) are compiled by CI and published to GitHub Releases (`release` branch). Do NOT mix Tier-1 and Tier-2 files for the same group — rules would evaluate twice.

`rulesets.json` (published to `ruleset/mihomo/` branch) is the inventory of all available split files, keyed by group slug. The web profile builder fetches this at runtime to know which splits exist.

### Profile builder (web — primary)

```bash
make dev            # Bun dev server at http://localhost:5173 (uses CDN rulesets)
make dev-local      # dev server using local dist/ instead of CDN
make web-build      # production build → web/dist/
```

The dev server hot-reloads on JS/HTML changes. `RULESET_DIR=../dist` env var (set by `make dev-local`) makes the server proxy ruleset requests to local build output.

### Profile builder (CLI)

```bash
cp profiles/user.yaml.example profiles/user.yaml
# edit profiles/user.yaml to add subscription URLs
make profile                         # builds standard preset → profiles/output/standard.yaml
make profile PRESET=full             # specific preset
./bin/hajimihomo --preset mini       # compiled binary (make cli-build first)
```

---

## Source Config Editing

### `source/categories.yaml`

Each entry is a leaf category. Key fields:

```yaml
CategoryName:
  version: 1
  type: domain      # domain | ip | mixed | unknown
  disabled: false   # set true to exclude from all builds
  sources:
    - repo:blackmatrix7/ios_rule_script/master/rule/Clash/CategoryName/CategoryName.list
    - https://example.com/rules.txt
  appends: []       # extra rules added on top
  removes: []       # rules removed from resolved set
  override:filename # prefix: replaces source entirely with local overrides/filename
```

Source URL schemes: `https://`, `repo:<owner>/<repo>/<branch>/<path>` (fetched from local vendor clone or GitHub raw), `file:<path>` (local file).

### `source/catalog.yaml`

Defines the 24 policy groups used in generated profiles. Key fields:

```yaml
groups:
  proxy/apple:
    name: "Apple Services"
    default_action: PROXY
    members: [Apple, AppStore, iCloud, ...]    # leaf category names
    excludes: [SomeCategory]                   # subtract from result
    members_ref: [proxy/google]               # union another catalog group
    excludes_ref: [direct/cn]                 # subtract another catalog group
```

After editing catalog.yaml, rebuild with `make build-groups` to verify resolution.

---

## Adding / Modifying Rules

1. **New category**: add entry to `source/categories.yaml` with sources.
2. **New policy group**: add entry to `source/catalog.yaml` with members.
3. **Override a source entirely**: create `source/overrides/<filename>`, set `override:filename` on the category.
4. **Validate**: `make validate` then `make build-dry`.
5. **Build**: `make build-groups` (faster than full build for catalog changes).

---

## Web Profile Builder

The UI runs at `http://localhost:5173` in dev mode. Key behavior:

- **Kernel selector**: `mihomo` / `mihomo-smart` (vernesong fork, enables `smart` group type) / `sing-box` (route fragment only)
- **Topology**: `full` (LB + url-test per region, ~60 groups) / `standard` (~25) / `minimal` (~12)
- **Geodata source**: `MetaCubeX (lite)` / `DustinWin (full)` — controls the `geox-url:` block. We do **not** publish our own geoip/geosite; always use a third-party source.
- **Ruleset format**: `Classic YAML` / `Split YAML` (default) / `Binary .mrs` — controls which dist file tier rule-providers reference. Binary requires CI releases to be published first.
- **Preset selector**: loads `presets.json` (generated from `profiles/presets/*.yaml` at build time); auto-applies topology, features, and group selection
- **Output**: for mihomo targets, generates a complete standalone YAML (DNS, sniffer, TUN, YAML anchors, proxy groups, rules); for sing-box, generates a route fragment

When modifying the profile generation logic, all logic lives in `web/src/ProfileBuilder.js` — the `buildFullProfile()` function at the bottom of that file. The Bun CLI (`web/cli.ts`) calls it directly. Static config defaults (DNS, sniffer, TUN, core settings) live in `profiles/defaults/mihomo.yaml` and are imported as text at build time.

Rule-provider URLs in generated profiles use jsDelivr CDN (`@ruleset` branch) for YAML split files, and `releases/latest/download/` for binary `.mrs` files (require CI release to exist).

**`geox-url` must point at a third-party geodata source** — we never publish `geoip.mmdb` or `geosite.dat`. Two supported sources (see P2b in plan):
- MetaCubeX/meta-rules-dat: `releases/download/latest/geosite.dat`, `geoip-lite.dat`, `country-lite.mmdb`, `GeoLite2-ASN.mmdb`
- DustinWin/ruleset_geodata: `releases/download/mihomo-geodata/geosite.dat`, `geoip.metadb`, `Country.mmdb`, `Country-ASN.mmdb`

---

## CI / CD

All CI targets `dev` branch. Workflows:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `build.yml` | push to `dev` (source/scripts), daily cron 19:00 UTC | Build rule sets, push to `ruleset` branch, compile binaries, push to `release` branch, purge CDN |
| `pages.yml` | push to `dev` (web/) | Build web app, deploy to `gh-pages` |
| `validate.yml` | PR to `dev` (source/) | Run `scripts/validate.py` |

The CI Python environment uses Python 3.12 with only `pyyaml` installed. Scripts run under CI must not import `jinja2`, `ruamel.yaml`, or `requests`.

---

## Naming Conventions

- **Catalog group IDs**: slash-separated tiers — `block/ads`, `proxy/apple`, `meta/cn`
- **Dist file stems**: slashes replaced with dashes — `proxy-apple.domain.yaml`, `proxy-apple.ip.yaml`
- **Rule-provider keys** in generated profiles: same as dist stem (e.g. `proxy-apple`, `proxy-apple-ip`)
- **Category names**: PascalCase matching blackmatrix7 naming — `Apple`, `GoogleDrive`, `AdvertisingLite`
- **Preset files**: numbered prefix for sort order — `1-mini.yaml`, `2-lite.yaml`, `3-standard.yaml`, `4-full.yaml`

---

## Common Gotchas

- **`dist/` is gitignored** — never commit build output. CDN branches (`ruleset`, `release`) are push-only from CI.
- **`vendor/` is gitignored** — run `make vendor-sync` to populate it locally.
- **`profiles/output/` is gitignored** — CLI profile builder output stays local.
- **YAML anchor syntax**: generated profiles use top-level dummy keys (`p:`, `g:`, `f:`) as anchor holders. mihomo ignores unknown top-level keys, so anchors defined there are valid and available throughout the document.
- **Rule ordering is critical**: in generated profiles, `direct/cn` domain rules MUST precede proxy service domain rules. Changing rule order in `ProfileBuilder.js` can cause CN traffic to leak through proxy.
- **Block groups use named selects, not direct REJECT**: rules never hardcode `REJECT` as a target. Instead, `block/ads` → `🚫 广告拦截` group (select: [REJECT, DIRECT, 默认代理]), etc. This allows dashboard-level toggle between blocking and bypassing without editing YAML.
- **`smart` group type** is NOT in official MetaCubeX/mihomo — it exists only in the `vernesong/mihomo` fork. The `mihomo-smart` kernel option in the web UI generates profiles that require this fork.
- **CI Python scripts**: CI uses system Python 3.12 + pyyaml only. Never add `jinja2`/`ruamel.yaml`/`requests` imports to `scripts/build.py`, `validate.py`, or other CI-run scripts.
- **Unquoted colon-space in YAML strings** is parsed as a nested mapping. Region filter regexes and other strings containing `: ` must be single-quoted in generated YAML output.

---

## Pull Request Guidelines

- All PRs target `dev` branch.
- For source changes: run `make validate` and `make build-dry` before opening a PR.
- For web changes: run `make web-build` to confirm the build passes.
- Commit message format: `type(scope): description` — e.g. `feat(catalog): add proxy/finance group`, `fix(build): correct ip-resolve ordering`.
- Include `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` trailer on AI-assisted commits.
