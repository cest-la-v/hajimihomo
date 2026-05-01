#!/usr/bin/env python3
"""
hajimihomo build orchestrator.

Reads source/rule/*/sources.yaml, downloads upstream rule files, deduplicates,
and emits:
  dist/mihomo/<Category>.yaml   — mihomo rule-provider YAML
  dist/singbox/<Category>.json  — sing-box rule-set JSON (version 3)

Usage:
  python3 scripts/build.py [--categories cat1,cat2,...] [--jobs N] [--dry-run]
"""

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import time
from pathlib import Path

import yaml  # PyYAML

# allow `from convert.xxx import` when running from repo root
sys.path.insert(0, str(Path(__file__).parent))

from convert.parse import fetch_and_parse
from convert.mihomo import detect_behavior, to_yaml as to_mihomo_yaml
from convert.singbox import to_json as to_singbox_json

# ---------------------------------------------------------------------------
# Categories excluded from build (derived unions / too many sources / dead)
# ---------------------------------------------------------------------------
SKIP_CATEGORIES: set[str] = {
    "ChinaMax",
    "ChinaMaxNoIP",
    "Global",
    "GlobalMedia",
    "ProxyLite",
    "Proxy",       # 300-source derived union; revisit if needed
}

log = logging.getLogger("build")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_sources(source_dir: Path) -> dict[str, list[str]]:
    """Return {category: [url, ...]} from source/rule/*/sources.yaml."""
    result: dict[str, list[str]] = {}
    for f in sorted(source_dir.glob("*/sources.yaml")):
        category = f.parent.name
        if category in SKIP_CATEGORIES:
            continue
        data = yaml.safe_load(f.read_text())
        urls = data.get("sources", [])
        if urls:
            result[category] = urls
    return result


def build_category(
    category: str,
    urls: list[str],
    dist: Path,
    dry_run: bool = False,
) -> dict:
    """Download, parse, deduplicate, and emit outputs for one category."""
    t0 = time.monotonic()
    all_rules: list[tuple[str, str]] = []
    errors: list[str] = []

    for url in urls:
        try:
            rules = fetch_and_parse(url)
            all_rules.extend(rules)
            log.debug("  %s: %d rules from %s", category, len(rules), url)
        except RuntimeError as e:
            log.warning("  %s: skip — %s", category, e)
            errors.append(str(e))

    # global deduplication
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for item in all_rules:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    behavior = detect_behavior(deduped)
    elapsed = time.monotonic() - t0

    meta = {
        "category": category,
        "rule_count": len(deduped),
        "behavior": behavior,
        "source_count": len(urls),
        "fetch_errors": len(errors),
        "elapsed_s": round(elapsed, 2),
    }

    if dry_run:
        log.info("  [dry-run] %s: %d rules (%s)", category, len(deduped), behavior)
        return meta

    # write outputs
    (dist / "mihomo").mkdir(parents=True, exist_ok=True)
    (dist / "singbox").mkdir(parents=True, exist_ok=True)

    mihomo_path = dist / "mihomo" / f"{category}.yaml"
    singbox_path = dist / "singbox" / f"{category}.json"

    mihomo_path.write_text(to_mihomo_yaml(deduped, category))
    singbox_path.write_text(to_singbox_json(deduped, category))

    log.info("  %s: %d rules (%s) in %.1fs", category, len(deduped), behavior, elapsed)
    return meta


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="hajimihomo build")
    parser.add_argument("--categories", help="comma-separated list; default: all")
    parser.add_argument("--jobs", type=int, default=8, help="parallel downloads (default: 8)")
    parser.add_argument("--dry-run", action="store_true", help="parse only, no file output")
    parser.add_argument("--source-dir", default="source/rule", help="path to source rules")
    parser.add_argument("--dist-dir", default="dist", help="output directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).parent.parent
    source_dir = repo_root / args.source_dir
    dist = repo_root / args.dist_dir

    all_sources = load_sources(source_dir)

    if args.categories:
        wanted = set(args.categories.split(","))
        all_sources = {k: v for k, v in all_sources.items() if k in wanted}

    log.info("Building %d categories with %d workers", len(all_sources), args.jobs)

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(build_category, cat, urls, dist, args.dry_run): cat
            for cat, urls in all_sources.items()
        }
        for future in concurrent.futures.as_completed(futures):
            cat = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                log.error("  %s: FAILED — %s", cat, e)
                results.append({"category": cat, "error": str(e)})

    # write build-meta.json
    if not args.dry_run:
        dist.mkdir(parents=True, exist_ok=True)
        meta = {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "categories": {r["category"]: r for r in results},
            "total_categories": len(results),
            "total_rules": sum(r.get("rule_count", 0) for r in results),
        }
        (dist / "build-meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
        )
        log.info(
            "Done: %d categories, %d total rules",
            meta["total_categories"],
            meta["total_rules"],
        )


if __name__ == "__main__":
    main()
