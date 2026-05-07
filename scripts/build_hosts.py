#!/usr/bin/env python3
"""
build_hosts.py — build a hosts: block for a mihomo profile.

Queries Cloudflare, Google, and Quad9 DoH for each polluted domain.
Keeps IPs returned by ≥2/3 providers (quorum). Results are cached
in source/hosts/.cache.json for 24 hours for deterministic builds.

source/hosts/overrides.yaml takes priority over DoH results.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
HOSTS_DIR  = REPO_ROOT / "source" / "hosts"
CACHE_FILE = HOSTS_DIR / ".cache.json"
CACHE_TTL  = 86400  # 24 hours

DOH_PROVIDERS = [
    ("cloudflare", "https://cloudflare-dns.com/dns-query"),
    ("google",     "https://dns.google/resolve"),
    ("quad9",      "https://dns.quad9.net/dns-query"),
]

TIMEOUT = 5
RETRIES = 2


def _doh_query(provider_url: str, domain: str) -> set[str]:
    """Return set of A-record IPs from one DoH provider."""
    for attempt in range(RETRIES + 1):
        try:
            r = requests.get(
                provider_url,
                params={"name": domain, "type": "A"},
                headers={"Accept": "application/dns-json"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return {
                ans["data"]
                for ans in data.get("Answer", [])
                if ans.get("type") == 1  # A record
            }
        except Exception:
            if attempt == RETRIES:
                return set()
            time.sleep(1)
    return set()


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def _resolve(domain: str, cache: dict) -> list[str] | None:
    """Return quorum IP list or None if no quorum. Uses cache if fresh."""
    now = time.time()
    if domain in cache and now - cache[domain]["ts"] < CACHE_TTL:
        return cache[domain]["ips"]

    results: list[set[str]] = []
    for name, url in DOH_PROVIDERS:
        ips = _doh_query(url, domain)
        results.append(ips)

    # Quorum: IPs present in ≥2 of 3 responses
    all_ips: set[str] = set()
    for s in results:
        all_ips |= s

    quorum_ips = sorted(
        ip for ip in all_ips
        if sum(1 for s in results if ip in s) >= 2
    )

    if not quorum_ips:
        print(f"  [warn] No quorum for {domain} — skipping", file=sys.stderr)
        cache[domain] = {"ts": now, "ips": None}
        return None

    cache[domain] = {"ts": now, "ips": quorum_ips}
    return quorum_ips


def build_hosts(
    hosts_include: list[str] | None = None,
    hosts_exclude: list[str] | None = None,
) -> str:
    """Return YAML fragment (indented 2 spaces) for the hosts: block."""
    polluted = yaml.safe_load((HOSTS_DIR / "polluted.yaml").read_text()) or []
    overrides_raw = yaml.safe_load((HOSTS_DIR / "overrides.yaml").read_text()) or {}
    overrides: dict[str, list[str]] = {
        d: ([v] if isinstance(v, str) else v)
        for d, v in overrides_raw.items()
    }

    hosts_include = hosts_include or []
    hosts_exclude = set(hosts_exclude or [])

    cache = _load_cache()
    lines: list[str] = []
    last_category = None

    for entry in polluted:
        domain = entry["domain"]
        category = entry.get("category", "")
        enabled = entry.get("enabled", False)

        # Selection logic (in precedence order)
        if domain in hosts_exclude:
            continue
        if hosts_include and domain not in hosts_include:
            continue
        if not hosts_include and not enabled:
            continue

        # Category comment header
        if category != last_category:
            lines.append(f"  # {category}")
            last_category = category

        if domain in overrides:
            ips = overrides[domain]
        else:
            ips = _resolve(domain, cache)
            if ips is None:
                continue

        if len(ips) == 1:
            lines.append(f"  '{domain}': '{ips[0]}'")
        else:
            lines.append(f"  '{domain}':")
            for ip in ips:
                lines.append(f"    - '{ip}'")

    _save_cache(cache)

    if not lines:
        return ""

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"  # updated: {ts}\n" + "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build hosts block from DoH cross-validation")
    parser.add_argument("--include", nargs="*", default=[], help="domains to include")
    parser.add_argument("--exclude", nargs="*", default=[], help="domains to exclude")
    args = parser.parse_args()

    result = build_hosts(hosts_include=args.include, hosts_exclude=args.exclude)
    if result:
        print("hosts:")
        print(result)
    else:
        print("# No hosts entries (all skipped or no quorum)", file=sys.stderr)
