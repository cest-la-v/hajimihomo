#!/usr/bin/env python3
"""
hajimihomo build orchestrator.

Reads source/rule/*/sources.yaml, resolves sub-rule includes/excludes from
source/rule/relationships.yaml, downloads upstream rule files, applies semantic
compression, and emits:
  dist/mihomo/<Category>.yaml         — mihomo rule-provider YAML (behavior auto-detected)
  dist/mihomo/<Category>_Domain.yaml  — domain-only subset for classical categories
  dist/singbox/<Category>.json        — sing-box rule-set JSON (version 3)

Usage:
  python3 scripts/build.py [--categories cat1,cat2,...] [--jobs N] [--dry-run]
"""

import argparse
import concurrent.futures
import json
import logging
import threading
import time
from pathlib import Path

import yaml  # PyYAML

import sys
sys.path.insert(0, str(Path(__file__).parent))

from convert.parse import fetch_and_parse
from convert.compress import compress
from convert.mihomo import detect_behavior, to_yaml as to_mihomo_yaml, to_domain_yaml
from convert.singbox import to_json as to_singbox_json

# ---------------------------------------------------------------------------
# Categories excluded from OUTPUT emission (still resolved as dependencies)
# ---------------------------------------------------------------------------
SKIP_CATEGORIES: set[str] = {
    "ChinaMax",
    "ChinaMaxNoIP",
    "ChinaMaxNoMedia",
    "Global",
    "ProxyLite",
    "Proxy",
}

log = logging.getLogger("build")


# ---------------------------------------------------------------------------
# Rule resolver — memoized recursive includes/excludes resolution
# ---------------------------------------------------------------------------

class RuleResolver:
    """
    Resolves the effective rule set for a category by recursively expanding
    includes and subtracting excludes, matching the blackmatrix7 RULE GENERATOR.

    effective(cat) = parse(direct_sources(cat))
                     ∪ effective(included)   for each included sub-category
                     - effective(excluded)   for each excluded category

    Results are memoized; thread-safe for parallel builds (last-write-wins on
    cache is safe because results are deterministic).
    """

    def __init__(
        self,
        sources: dict[str, list[str]],
        includes: dict[str, list[str]],
        excludes: dict[str, list[str]],
    ) -> None:
        self._sources = sources
        self._includes = includes
        self._excludes = excludes
        self._cache: dict[str, frozenset[tuple[str, str]]] = {}
        self._lock = threading.Lock()

    def effective_rules(
        self,
        category: str,
        _stack: frozenset[str] = frozenset(),
    ) -> frozenset[tuple[str, str]]:
        """Return the fully resolved (includes absorbed, excludes stripped) rule set."""
        # Fast path: already computed
        with self._lock:
            if category in self._cache:
                return self._cache[category]

        # Cycle guard (should not happen in practice)
        if category in _stack:
            log.warning("Cycle detected resolving %s (stack: %s) — skipping", category, _stack)
            return frozenset()

        new_stack = _stack | {category}
        rules: set[tuple[str, str]] = set()

        # 1. Direct sources for this category
        for url in self._sources.get(category, []):
            try:
                rules.update(fetch_and_parse(url))
                log.debug("  %s: fetched %s", category, url)
            except RuntimeError as e:
                log.warning("  %s: skip source — %s", category, e)

        # 2. Absorb included sub-categories
        for inc in self._includes.get(category, []):
            rules.update(self.effective_rules(inc, new_stack))

        # 3. Subtract excluded categories
        for exc in self._excludes.get(category, []):
            rules -= self.effective_rules(exc, new_stack)

        result = frozenset(rules)
        with self._lock:
            self._cache[category] = result
        return result


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_all_sources(source_dir: Path) -> dict[str, list[str]]:
    """Return {category: [url, ...]} for ALL categories (no SKIP filtering)."""
    result: dict[str, list[str]] = {}
    for f in sorted(source_dir.glob("*/sources.yaml")):
        category = f.parent.name
        data = yaml.safe_load(f.read_text())
        urls = data.get("sources", [])
        if urls:
            result[category] = urls
    return result


def load_relationships(source_dir: Path) -> tuple[dict, dict]:
    """Return (includes_map, excludes_map) from relationships.yaml."""
    rel_path = source_dir / "relationships.yaml"
    if not rel_path.exists():
        log.warning("relationships.yaml not found at %s — no includes/excludes applied", rel_path)
        return {}, {}
    data = yaml.safe_load(rel_path.read_text()) or {}
    return data.get("includes", {}), data.get("excludes", {})


# ---------------------------------------------------------------------------
# Per-category build
# ---------------------------------------------------------------------------

def build_category(
    category: str,
    resolver: RuleResolver,
    dist: Path,
    dry_run: bool = False,
) -> dict:
    """Resolve, compress, and emit outputs for one category."""
    t0 = time.monotonic()

    raw_rules = resolver.effective_rules(category)
    rules = compress(list(raw_rules))

    behavior = detect_behavior(rules)
    elapsed = time.monotonic() - t0

    meta = {
        "category": category,
        "rule_count": len(rules),
        "behavior": behavior,
        "elapsed_s": round(elapsed, 2),
    }

    if dry_run:
        log.info("  [dry-run] %s: %d rules (%s)", category, len(rules), behavior)
        return meta

    (dist / "mihomo").mkdir(parents=True, exist_ok=True)
    (dist / "singbox").mkdir(parents=True, exist_ok=True)

    (dist / "mihomo" / f"{category}.yaml").write_text(to_mihomo_yaml(rules, category))
    (dist / "singbox" / f"{category}.json").write_text(to_singbox_json(rules, category))

    # Emit domain-only split for classical categories (enables behavior:domain + .mrs)
    if behavior == "classical":
        domain_yaml = to_domain_yaml(rules, category)
        if domain_yaml:
            (dist / "mihomo" / f"{category}_Domain.yaml").write_text(domain_yaml)

    log.info("  %s: %d rules (%s) in %.1fs", category, len(rules), behavior, elapsed)
    return meta


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="hajimihomo build")
    parser.add_argument("--categories", help="comma-separated list; default: all")
    parser.add_argument("--jobs", type=int, default=8, help="parallel workers (default: 8)")
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

    all_sources = load_all_sources(source_dir)
    includes_map, excludes_map = load_relationships(source_dir)

    resolver = RuleResolver(all_sources, includes_map, excludes_map)

    # Determine categories to emit (SKIP_CATEGORIES excluded from output only)
    emit_cats: dict[str, None] = {
        cat: None
        for cat in sorted(all_sources)
        if cat not in SKIP_CATEGORIES
    }

    if args.categories:
        wanted = set(args.categories.split(","))
        emit_cats = {k: v for k, v in emit_cats.items() if k in wanted}

    log.info("Building %d categories with %d workers", len(emit_cats), args.jobs)

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(build_category, cat, resolver, dist, args.dry_run): cat
            for cat in emit_cats
        }
        for future in concurrent.futures.as_completed(futures):
            cat = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                log.error("  %s: FAILED — %s", cat, e)
                results.append({"category": cat, "error": str(e)})

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
