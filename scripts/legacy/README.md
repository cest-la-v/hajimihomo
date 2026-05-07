# Legacy Python profile builder

These scripts have been superseded by the Bun CLI (`web/cli.ts`).

| Script | Replaced by |
|--------|-------------|
| `build_profile.py` | `web/cli.ts` + `make profile` |
| `gen_proxy_groups.py` | `web/src/ProfileBuilder.js` → `_buildProxyGroups()` |
| `gen_rules.py` | `web/src/ProfileBuilder.js` → `_buildRuleProvidersForFormat()` / `_buildRules2()` |

The Jinja2 template (`profiles/templates/mihomo.yaml.j2`) is also superseded.
Use `make profile` to generate profiles via the Bun CLI.
