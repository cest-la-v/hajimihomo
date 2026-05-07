#!/usr/bin/env python3
"""
build_profile.py — generate a complete, standalone mihomo profile YAML.

Usage:
  python3 scripts/build_profile.py [--preset mini|lite|standard|full]
                                   [--user profiles/user.yaml]
                                   [--output profiles/output/]

The generated profile is ready to use with mihomo after adding proxy
subscription URLs in profiles/user.yaml.

Rule-provider URLs reference the jsDelivr CDN (@ruleset branch).
These resolve once CI has published the ruleset branch.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from ruamel.yaml import YAML as RuamelYAML

REPO_ROOT     = Path(__file__).resolve().parent.parent
PRESETS_DIR   = REPO_ROOT / "profiles" / "presets"
TEMPLATES_DIR = REPO_ROOT / "profiles" / "templates"
OUTPUT_DIR    = REPO_ROOT / "profiles" / "output"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from gen_proxy_groups import build as build_proxy_groups
from gen_rules         import build as build_rules
from build_hosts       import build_hosts


# ── preset / user loading ─────────────────────────────────────────────────────

def load_preset(name: str) -> dict:
    path = PRESETS_DIR / f"{name}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in PRESETS_DIR.glob("*.yaml"))
        sys.exit(f"Unknown preset '{name}'. Available: {', '.join(available)}")
    data = yaml.safe_load(path.read_text())
    # Defaults for older presets without full schema
    data.setdefault("target", "mihomo")
    data.setdefault("topology", "regional")
    data.setdefault("geodata", "metacubex")
    data.setdefault("features", {})
    data["features"].setdefault("ads_block", True)
    data["features"].setdefault("tracking_block", False)
    data["features"].setdefault("quic_block", False)
    data["features"].setdefault("load_balance", False)
    data.setdefault("groups", [])
    return data


def load_user(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def merge_config(preset: dict, user: dict) -> dict:
    """Merge user.yaml on top of preset (additive for groups)."""
    cfg = dict(preset)
    # User may override target and topology
    if "target" in user:
        cfg["target"] = user["target"]
    if "topology" in user:
        cfg["topology"] = user["topology"]
    if "features" in user:
        cfg["features"].update(user["features"])

    # Group list: start from preset, apply extra_groups and skip_groups
    groups = list(cfg["groups"])
    for g in user.get("extra_groups", []):
        if g not in groups:
            groups.append(g)
    skip = set(user.get("skip_groups", []))
    cfg["groups"] = [g for g in groups if g not in skip]

    cfg["region_excludes"]  = user.get("region_excludes", "")
    cfg["hosts_enabled"]    = user.get("hosts_enabled", False)
    cfg["hosts_include"]    = user.get("hosts_include", [])
    cfg["hosts_exclude"]    = user.get("hosts_exclude", [])
    cfg["proxy_providers"]  = user.get("proxy_providers", [])
    cfg["geodata"]          = user.get("geodata", preset.get("geodata", "metacubex"))
    return cfg


# ── proxy-providers block ─────────────────────────────────────────────────────

def build_proxy_providers_yaml(providers: list[dict]) -> str:
    if not providers:
        return "  # Add your proxy subscriptions in profiles/user.yaml\n  # example:\n  # - name: 主力机场\n  #   <<: *BaseProvider\n  #   url: 'https://your-airport.com/subscribe?token=xxx'\n  #   prefix: '[主] '"
    lines: list[str] = []
    for p in providers:
        name = p.get("name", "provider")
        url  = p.get("url", "")
        prefix = p.get("prefix", "")
        lines += [
            f"  {name}:",
            f"    <<: *BaseProvider",
            f"    type: http",
            f"    url: '{url}'",
        ]
        if prefix:
            lines.append(f"    override:")
            lines.append(f"      additional-prefix: '{prefix}'")
    return "\n".join(lines)


# ── validation ────────────────────────────────────────────────────────────────

def validate_output(rendered: str, preset_name: str) -> None:
    """Parse rendered YAML and check internal group reference integrity."""
    ry = RuamelYAML()
    ry.preserve_quotes = True
    import io
    try:
        doc = ry.load(io.StringIO(rendered))
    except Exception as e:
        sys.exit(f"[error] Generated profile for '{preset_name}' is not valid YAML:\n  {e}")

    # Collect all defined group names
    groups_defined: set[str] = set()
    for g in (doc.get("proxy-groups") or []):
        if hasattr(g, "get"):
            n = g.get("name")
            if n:
                groups_defined.add(str(n))

    # Check all proxy references in groups resolve
    errors: list[str] = []
    builtin = {"DIRECT", "REJECT", "COMPATIBLE"}
    for g in (doc.get("proxy-groups") or []):
        if not hasattr(g, "get"):
            continue
        gname = g.get("name", "?")
        for ref in g.get("proxies") or []:
            ref_s = str(ref)
            if ref_s not in groups_defined and ref_s not in builtin:
                errors.append(f"  group '{gname}' references unknown proxy '{ref_s}'")

    if errors:
        sys.exit(
            f"[error] Reference integrity failures in '{preset_name}':\n"
            + "\n".join(errors)
        )

    print(f"  [ok] YAML valid, {len(groups_defined)} groups, no broken references")


# ── main ──────────────────────────────────────────────────────────────────────

def build_profile(preset_name: str, user_path: Path | None, output_dir: Path) -> None:
    preset = load_preset(preset_name)
    user   = load_user(user_path)
    cfg    = merge_config(preset, user)

    target   = cfg["target"]
    topology = cfg["topology"]
    features = cfg["features"]
    groups   = cfg["groups"]
    geodata  = cfg.get("geodata", "metacubex")

    if target == "sing-box":
        sys.exit("[error] sing-box output is not supported in P1 — planned for P2.")

    # Backward-compat: old topology names (pre-rename)
    _TOPOLOGY_ALIASES = {"minimal": "global", "standard": "regional", "full": "advanced"}
    topology = _TOPOLOGY_ALIASES.get(topology, topology)

    exclude_filter = cfg.get("region_excludes", "")

    print(f"Building preset '{preset_name}' (target={target}, topology={topology})...")
    print(f"  groups: {', '.join(groups)}")

    # Generate proxy-groups
    proxy_groups_yaml, service_map = build_proxy_groups(
        groups,
        topology=topology,
        target=target,
        features=features,
        region_excludes=exclude_filter,
    )

    # Generate rule-providers + rules
    rule_providers_yaml, rules_yaml = build_rules(
        groups,
        features=features,
        service_map=service_map,
    )

    # Proxy providers
    proxy_providers_yaml = build_proxy_providers_yaml(cfg["proxy_providers"])

    # Hosts block (optional)
    hosts_yaml = ""
    if cfg.get("hosts_enabled"):
        print("  Resolving hosts via DoH...")
        hosts_yaml = build_hosts(
            hosts_include=cfg.get("hosts_include"),
            hosts_exclude=cfg.get("hosts_exclude"),
        )

    # Render Jinja2 template
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template("mihomo.yaml.j2")
    rendered = template.render(
        target=target,
        topology=topology,
        features=features,
        geodata=geodata,
        exclude_filter=exclude_filter,
        proxy_providers=proxy_providers_yaml,
        proxy_groups=proxy_groups_yaml,
        rule_providers=rule_providers_yaml,
        rules=rules_yaml,
        hosts=hosts_yaml,
    )

    # Validate
    print("  Validating...")
    validate_output(rendered, preset_name)

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{preset_name}.yaml"
    out_path.write_text(rendered)
    print(f"  Written: {out_path.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a mihomo profile from a preset + user config"
    )
    parser.add_argument(
        "--preset", default="full",
        help="Preset name (mini|lite|standard|full, default: full)",
    )
    parser.add_argument(
        "--user", default=None,
        help="Path to user config (default: profiles/user.yaml if it exists)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output directory (default: profiles/output/)",
    )
    args = parser.parse_args()

    user_path = Path(args.user) if args.user else REPO_ROOT / "profiles" / "user.yaml"
    if not user_path.exists() and args.user:
        sys.exit(f"[error] User config not found: {user_path}")

    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    build_profile(args.preset, user_path if user_path.exists() else None, output_dir)


if __name__ == "__main__":
    main()
