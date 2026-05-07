#!/usr/bin/env python3
"""
gen_proxy_groups.py — generate proxy-groups block for a mihomo profile.

Topologies:
  advanced — Select → Fallback → LB-hash (hidden) + LB-rr (hidden) + url-test per region
  regional — Select → Fallback → url-test per region + per-service selects
  global   — Select (global url-test) + per-service selects pointing at 默认代理 only

smart groups: when target == 'mihomo-smart', url-test → smart (vernesong fork required)
"""
from __future__ import annotations

# ── region definitions ────────────────────────────────────────────────────────

REGIONS = [
    ("香港",  "FilterHK", "*FilterHK"),
    ("狮城",  "FilterSG", "*FilterSG"),
    ("日本",  "FilterJP", "*FilterJP"),
    ("韩国",  "FilterKR", "*FilterKR"),
    ("美国",  "FilterUS", "*FilterUS"),
    ("台湾",  "FilterTW", "*FilterTW"),
    ("欧盟",  "FilterEU", "*FilterEU"),
]

# Preferred region order for fallback group (only reliable regions)
FALLBACK_REGIONS = ["香港", "狮城", "日本", "美国"]

# ── service map: slug → (display name, preferred region proxies) ──────────────
# Per-service proxy candidates are topology-dependent (see build_service_group).
# This map defines the *label* and the *preferred regions* for full/standard.
SERVICE_MAP: dict[str, tuple[str, list[str]]] = {
    "block/ads":         ("🚫 广告拦截",  []),           # REJECT target, handled separately
    "block/ads-lite":    ("🚫 广告(轻)",  []),
    "block/tracking":    ("🕵 追踪拦截",  []),
    "direct/cn":         ("🇨🇳 直连",    []),           # DIRECT, handled separately
    "direct/cn-ips":     ("🇨🇳 直连IP",  []),
    "direct/cn-no-media":("🇨🇳 直连(无媒体)", []),
    "proxy/google":      ("🔍 Google",   ["香港", "美国", "默认代理"]),
    "proxy/youtube":     ("▶️  YouTube",  ["香港", "美国", "默认代理"]),
    "proxy/apple":       ("🍎 Apple",    ["直接连接", "香港", "美国"]),
    "proxy/microsoft":   ("🪟 Microsoft",["默认代理", "直接连接"]),
    "proxy/amazon":      ("📦 Amazon",   ["美国", "默认代理"]),
    "proxy/telegram":    ("✈️  Telegram", ["香港", "狮城", "默认代理"]),
    "proxy/twitter":     ("🐦 Twitter",  ["香港", "美国", "默认代理"]),
    "proxy/netflix":     ("🎬 Netflix",  ["狮城", "香港", "默认代理"]),
    "proxy/streaming":   ("🎥 Streaming",["狮城", "香港", "默认代理"]),
    "proxy/social":      ("💬 Social",   ["香港", "默认代理"]),
    "proxy/ai":          ("🤖 AI",       ["美国", "默认代理"]),
    "proxy/gaming":      ("🎮 Gaming",   ["香港", "日本", "默认代理"]),
    "proxy/dev":         ("💻 Dev",      ["默认代理", "直接连接"]),
    "proxy/finance":     ("💰 Finance",  ["香港", "默认代理"]),
    "proxy/news":        ("📰 News",     ["默认代理"]),
    "meta/block":        ("🚫 Meta拦截", []),
    "meta/cn":           ("🇨🇳 Meta直连",[]),
    "meta/foreign":      ("🌐 Meta外网", ["默认代理"]),
}

_DIRECT_GROUPS = {"direct/cn", "direct/cn-ips", "direct/cn-no-media", "meta/cn"}
_REJECT_GROUPS = {"block/ads", "block/ads-lite", "block/tracking", "meta/block"}
_INFRA_GROUPS  = _DIRECT_GROUPS | _REJECT_GROUPS


def _region_auto_type(target: str) -> str:
    return "smart" if target == "mihomo-smart" else "url-test"


def _auto_group(name: str, filter_anchor: str, target: str, *, hidden: bool = True) -> dict:
    kind = _region_auto_type(target)
    g: dict = {
        "name": name,
        "type": kind,
        "include-all": True,
        "filter": f"'{filter_anchor}'",
        "lazy": True,
    }
    if kind == "url-test":
        g["url"] = "https://www.google.com/generate_204"
        g["interval"] = 200
    if kind == "smart":
        g["uselightgbm"] = True
    if hidden:
        g["hidden"] = True
    return g


def _yaml_group(g: dict, indent: int = 2) -> list[str]:
    """Render a group dict as indented YAML lines (simple key: value only)."""
    pad = " " * indent
    lines = [f"{pad}- name: '{g['name']}'"]
    skip = {"name"}
    for k, v in g.items():
        if k in skip:
            continue
        if isinstance(v, bool):
            lines.append(f"{pad}  {k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{pad}  {k}: {v}")
        elif isinstance(v, list):
            lines.append(f"{pad}  {k}:")
            for item in v:
                lines.append(f"{pad}    - '{item}'")
        else:
            # string — already quoted by caller if needed, or plain
            sv = str(v)
            if sv.startswith("'") or sv.startswith('"'):
                lines.append(f"{pad}  {k}: {sv}")
            else:
                lines.append(f"{pad}  {k}: '{sv}'")
    return lines


def _select(name: str, proxies: list[str]) -> list[str]:
    lines = [f"  - name: '{name}'", f"    type: select", f"    proxies:"]
    for p in proxies:
        lines.append(f"      - '{p}'")
    return lines


def _fallback(name: str, proxies: list[str]) -> list[str]:
    lines = [
        f"  - name: '{name}'",
        f"    type: fallback",
        f"    url: 'https://www.google.com/generate_204'",
        f"    interval: 200",
        f"    lazy: true",
        f"    proxies:",
    ]
    for p in proxies:
        lines.append(f"      - '{p}'")
    return lines


def build(
    group_ids: list[str],
    *,
    topology: str = "standard",
    target: str = "mihomo",
    features: dict | None = None,
    region_excludes: str = "",
) -> tuple[str, dict[str, tuple[str, list[str]]]]:
    """
    Return (proxy_groups_yaml, effective_service_map).

    effective_service_map: slug → (display_name, preferred_proxies)
    This is passed to gen_rules so rule targets match generated group names.
    """
    features = features or {}
    out: list[str] = []

    # Which service groups are selected (not infra)
    service_groups = [g for g in group_ids if g not in _INFRA_GROUPS]

    # Build effective region list
    region_names = [r[0] for r in REGIONS]
    fallback_candidates = [r for r in FALLBACK_REGIONS if r in region_names]

    # ── infrastructure groups ─────────────────────────────────────────────────
    if topology in ("advanced", "regional"):
        main_proxies = ["故障转移"] + region_names + ["全部", "直接连接"]
        out += _select("默认代理", main_proxies)
        out += _fallback("故障转移", fallback_candidates)
    else:
        # global: no regional groups — direct url-test global only
        main_proxies = ["全部", "直接连接"]
        out += _select("默认代理", main_proxies)

    out += _select("直接连接", ["DIRECT", "默认代理"])

    # Named select groups for each reject category (never hardcode REJECT in rules)
    for gid in group_ids:
        if gid in _REJECT_GROUPS:
            display = SERVICE_MAP.get(gid, (f"🚫 {gid.split('/')[-1]}", []))[0]
            out += _select(display, ["REJECT", "DIRECT", "默认代理"])
    if features.get("quic_block"):
        out += _select("🛡️ 协议拦截", ["REJECT", "DIRECT", "默认代理"])

    # ── region groups ─────────────────────────────────────────────────────────
    if topology in ("advanced", "regional"):
        for region_name, _filter_key, filter_anchor in REGIONS:
            if topology == "advanced" and features.get("load_balance"):
                # hidden LB-hash sibling
                lbh = {
                    "name": f"{region_name}-LBH",
                    "type": "load-balance",
                    "strategy": "consistent-hashing",
                    "url": "https://www.google.com/generate_204",
                    "interval": 200,
                    "lazy": True,
                    "hidden": True,
                    "include-all": True,
                    "filter": f"'{filter_anchor}'",
                }
                out += _yaml_group(lbh)
                # hidden LB-rr sibling
                lbr = {
                    "name": f"{region_name}-LBR",
                    "type": "load-balance",
                    "strategy": "round-robin",
                    "url": "https://www.google.com/generate_204",
                    "interval": 200,
                    "lazy": True,
                    "hidden": True,
                    "include-all": True,
                    "filter": f"'{filter_anchor}'",
                }
                out += _yaml_group(lbr)

            # main url-test/smart region group (visible)
            ag = _auto_group(region_name, filter_anchor, target, hidden=False)
            out += _yaml_group(ag)

    # Global auto group (all providers, no region filter)
    all_ag = {
        "name": "全部",
        "type": _region_auto_type(target),
        "include-all": True,
        "filter": "'*FilterALL'",
        "lazy": True,
        "hidden": True,
    }
    if _region_auto_type(target) == "url-test":
        all_ag["url"] = "https://www.google.com/generate_204"
        all_ag["interval"] = 200
    if _region_auto_type(target) == "smart":
        all_ag["uselightgbm"] = True
    out += _yaml_group(all_ag)

    # ── per-service groups ────────────────────────────────────────────────────
    effective_service_map: dict[str, tuple[str, list[str]]] = {}

    for gid in service_groups:
        entry = SERVICE_MAP.get(gid)
        if entry:
            display, preferred = entry
        else:
            # fallback: prettify slug
            display = "🌐 " + gid.split("/")[-1].title()
            preferred = []

        if topology in ("advanced", "regional"):
            # filter preferred to only regions that exist + always include 默认代理/直接连接
            candidates = [p for p in preferred if p in region_names or p in ("默认代理", "直接连接")]
            if not candidates:
                candidates = ["默认代理", "直接连接"]
            if "默认代理" not in candidates:
                candidates.append("默认代理")
        else:
            # minimal: no regional groups
            candidates = ["默认代理", "直接连接"]

        effective_service_map[gid] = (display, candidates)
        out += _select(display, candidates)

    # ── catch-all ─────────────────────────────────────────────────────────────
    out += _select("漏网之鱼", ["默认代理", "直接连接"])

    # Include reject groups in effective_service_map so gen_rules can resolve targets
    for gid in group_ids:
        if gid in _REJECT_GROUPS:
            display = SERVICE_MAP.get(gid, (f"🚫 {gid.split('/')[-1]}", []))[0]
            effective_service_map[gid] = (display, ["REJECT", "DIRECT", "默认代理"])

    return "\n".join(out), effective_service_map


if __name__ == "__main__":
    yaml_out, smap = build(
        ["block/ads", "direct/cn", "direct/cn-ips", "proxy/apple", "proxy/google"],
        topology="standard",
        target="mihomo",
        features={"ads_block": True},
    )
    print("proxy-groups:")
    print(yaml_out)
