#!/usr/bin/env python3
"""
gen_rules.py — generate rule-providers and rules blocks for a mihomo profile.

Dist naming: proxy/apple → proxy-apple.domain.yaml / proxy-apple.ip.yaml
IP rule-provider included for a group when any member category has type
ip | mixed | unknown (conservative: unknown always gets both).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "source"
DIST_BASE_URL = "https://github.com/cest-la-v/hajimihomo/releases/latest/download"

# Groups that are pure-DIRECT (never get a proxy target)
DIRECT_GROUPS = {"direct/cn", "direct/cn-ips", "direct/cn-no-media"}
# Groups that REJECT rather than proxy
REJECT_GROUPS = {"block/ads", "block/ads-lite", "block/tracking", "meta/block"}


def slug(group_id: str) -> str:
    return group_id.replace("/", "-")


def _load_categories() -> dict[str, str]:
    """Return {category_name: type_str} from categories.yaml."""
    data = yaml.safe_load((SOURCE_DIR / "categories.yaml").read_text())
    return {
        name: entry.get("type", "unknown")
        for name, entry in (data.get("categories") or {}).items()
    }


def _load_catalog() -> dict:
    return yaml.safe_load((SOURCE_DIR / "catalog.yaml").read_text())


def _needs_ip_provider(group_id: str, catalog: dict, cat_types: dict[str, str]) -> bool:
    """True if any member category carries IP rules."""
    if group_id in DIRECT_GROUPS:
        # direct/cn-ips is IP-only; direct/cn domain only
        return group_id == "direct/cn-ips"
    members = catalog["groups"].get(group_id, {}).get("members", [])
    if not members:
        return False
    for m in members:
        t = cat_types.get(m, "unknown")
        if t in ("ip", "mixed", "unknown"):
            return True
    return False


def gen_rule_providers(
    group_ids: list[str],
    catalog: dict,
    cat_types: dict[str, str],
) -> str:
    lines: list[str] = []
    for gid in group_ids:
        s = slug(gid)
        # domain provider
        lines += [
            f"  {s}:",
            f"    type: http",
            f"    behavior: domain",
            f"    url: '{DIST_BASE_URL}/{s}.domain.yaml'",
            f"    path: './ruleset/{s}.domain.yaml'",
            f"    interval: 86400",
            f"    format: yaml",
        ]
        if _needs_ip_provider(gid, catalog, cat_types):
            lines += [
                f"  {s}-ip:",
                f"    type: http",
                f"    behavior: ipcidr",
                f"    url: '{DIST_BASE_URL}/{s}.ip.yaml'",
                f"    path: './ruleset/{s}.ip.yaml'",
                f"    interval: 86400",
                f"    format: yaml",
            ]
    return "\n".join(lines)


def gen_rules(
    group_ids: list[str],
    catalog: dict,
    cat_types: dict[str, str],
    *,
    service_map: dict[str, tuple[str, list[str]]],
    features: dict,
) -> str:
    lines: list[str] = []

    # 1. QUIC block
    if features.get("quic_block"):
        lines.append("  - AND,[[NETWORK,UDP],[DST-PORT,443]],REJECT")

    # 2. Reject groups (ads/tracking)
    for gid in group_ids:
        if gid in REJECT_GROUPS:
            lines.append(f"  - RULE-SET,{slug(gid)},REJECT")

    # 3. Direct CN domain rules (must precede proxy service rules)
    for gid in group_ids:
        if gid in DIRECT_GROUPS and gid != "direct/cn-ips":
            lines.append(f"  - RULE-SET,{slug(gid)},DIRECT")

    # 4. Proxy service domain rules
    for gid in group_ids:
        if gid in DIRECT_GROUPS or gid in REJECT_GROUPS:
            continue
        display_name = service_map.get(gid, (slug(gid), []))[0]
        lines.append(f"  - RULE-SET,{slug(gid)},{display_name}")

    # 5. Direct CN IP rules
    for gid in group_ids:
        if gid == "direct/cn-ips" or (
            gid in DIRECT_GROUPS and _needs_ip_provider(gid, catalog, cat_types)
        ):
            lines.append(f"  - RULE-SET,{slug(gid)}-ip,DIRECT,no-resolve")

    # 6. Proxy service IP rules
    for gid in group_ids:
        if gid in DIRECT_GROUPS or gid in REJECT_GROUPS:
            continue
        if _needs_ip_provider(gid, catalog, cat_types):
            display_name = service_map.get(gid, (slug(gid), []))[0]
            lines.append(f"  - RULE-SET,{slug(gid)}-ip,{display_name},no-resolve")

    # 7. Catch-all
    lines.append("  - MATCH,默认代理")

    return "\n".join(lines)


def build(
    group_ids: list[str],
    features: dict | None = None,
    service_map: dict | None = None,
) -> tuple[str, str]:
    """Return (rule_providers_yaml, rules_yaml) for the given group list."""
    features = features or {}
    service_map = service_map or {}
    catalog = _load_catalog()
    cat_types = _load_categories()

    rp = gen_rule_providers(group_ids, catalog, cat_types)
    rules = gen_rules(group_ids, catalog, cat_types, service_map=service_map, features=features)
    return rp, rules


if __name__ == "__main__":
    groups = sys.argv[1:] or ["block/ads", "direct/cn", "direct/cn-ips", "proxy/apple"]
    rp, rules = build(groups, features={"quic_block": True})
    print("rule-providers:")
    print(rp)
    print()
    print("rules:")
    print(rules)
