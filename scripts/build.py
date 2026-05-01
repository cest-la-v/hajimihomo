#!/usr/bin/env python3
"""
hajimihomo build orchestrator.

Two build targets:

1. Atomic categories — source/rule/*/sources.yaml (one file per bm7 category)
   Resolved with sub-rule includes/excludes from source/rule/relationships.yaml.

2. Catalog groups    — source/catalog.yaml (semantic bundles for policy groups)
   Each group unions effective_rules of its bm7 members: or other groups
   in members_ref:. IDs use slashes (proxy/google) → flat filenames (proxy-google).

Output per name:
  dist/mihomo/<name>.yaml         — mihomo rule-provider YAML
  dist/mihomo/<name>_Domain.yaml  — domain-only subset (for classical categories)
  dist/singbox/<name>.json        — sing-box rule-set JSON v3

Usage:
  python3 scripts/build.py [--categories cat1,...] [--groups grp1,...] [--jobs N]
  python3 scripts/build.py --all-groups   # catalog groups only, skip atomics
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


def load_catalog(catalog_path: Path) -> dict:
    """Return the raw catalog data from source/catalog.yaml."""
    if not catalog_path.exists():
        return {}
    return yaml.safe_load(catalog_path.read_text()) or {}


def resolve_catalog_group(
    group_id: str,
    catalog: dict,
    resolver: RuleResolver,
    _group_stack: frozenset[str] = frozenset(),
) -> frozenset[tuple[str, str]]:
    """
    Resolve a catalog group to its effective rule set.

    members:     → union of bm7 category effective_rules (via RuleResolver)
    members_ref: → union of other catalog groups (recursive)
    """
    if group_id in _group_stack:
        log.warning("Cycle in catalog groups: %s in %s — skipping", group_id, _group_stack)
        return frozenset()

    groups = catalog.get("groups", {})
    spec = groups.get(group_id)
    if spec is None:
        log.warning("Catalog group not found: %s", group_id)
        return frozenset()

    rules: set[tuple[str, str]] = set()
    new_stack = _group_stack | {group_id}

    # Direct bm7 category members
    for cat in spec.get("members", []):
        rules.update(resolver.effective_rules(cat))

    # References to other catalog groups
    for ref in spec.get("members_ref", []):
        rules.update(resolve_catalog_group(ref, catalog, resolver, new_stack))

    return frozenset(rules)


# ---------------------------------------------------------------------------
# Per-category build
# ---------------------------------------------------------------------------

def build_item(
    name: str,
    raw_rules: frozenset[tuple[str, str]],
    dist: Path,
    dry_run: bool = False,
) -> dict:
    """Compress and emit outputs for one named rule set."""
    t0 = time.monotonic()
    rules = compress(list(raw_rules))
    behavior = detect_behavior(rules)
    elapsed = time.monotonic() - t0

    meta = {
        "name": name,
        "rule_count": len(rules),
        "behavior": behavior,
        "elapsed_s": round(elapsed, 2),
    }

    if dry_run:
        log.info("  [dry-run] %s: %d rules (%s)", name, len(rules), behavior)
        return meta

    (dist / "mihomo").mkdir(parents=True, exist_ok=True)
    (dist / "singbox").mkdir(parents=True, exist_ok=True)

    (dist / "mihomo" / f"{name}.yaml").write_text(to_mihomo_yaml(rules, name))
    (dist / "singbox" / f"{name}.json").write_text(to_singbox_json(rules, name))

    if behavior == "classical":
        domain_yaml = to_domain_yaml(rules, name)
        if domain_yaml:
            (dist / "mihomo" / f"{name}_Domain.yaml").write_text(domain_yaml)

    log.info("  %s: %d rules (%s) in %.1fs", name, len(rules), behavior, elapsed)
    return meta


def build_category(
    category: str,
    resolver: RuleResolver,
    dist: Path,
    dry_run: bool = False,
) -> dict:
    """Resolve, compress, and emit an atomic bm7 category."""
    raw_rules = resolver.effective_rules(category)
    return build_item(category, raw_rules, dist, dry_run)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="hajimihomo build")
    parser.add_argument("--categories", help="comma-separated bm7 categories; default: all non-skipped")
    parser.add_argument("--groups", help="comma-separated catalog group IDs (e.g. proxy/google,meta/cn)")
    parser.add_argument("--all-groups", action="store_true", help="build catalog groups only (skip atomics)")
    parser.add_argument("--with-groups", action="store_true",
                        help="build all atomics AND all catalog groups (default CI mode)")
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
    catalog = load_catalog(repo_root / "source" / "catalog.yaml")

    resolver = RuleResolver(all_sources, includes_map, excludes_map)

    # ---- Collect work items: (name, callable_that_returns_frozenset) ----
    # Key: output file stem; value: callable producing raw frozenset of rules
    work: dict[str, any] = {}

    # Build atomics unless --all-groups is set or only --groups were requested
    build_atomics = not args.all_groups and not (args.groups and not args.categories)
    if build_atomics:
        emit_cats = [cat for cat in sorted(all_sources) if cat not in SKIP_CATEGORIES]
        if args.categories:
            wanted = set(args.categories.split(","))
            emit_cats = [c for c in emit_cats if c in wanted]
        for cat in emit_cats:
            work[cat] = lambda c=cat: resolver.effective_rules(c)

    # Catalog groups — built if --groups, --all-groups, or --with-groups
    if args.all_groups or args.with_groups or args.groups:
        catalog_groups = catalog.get("groups", {})
        if args.groups:
            wanted_groups = args.groups.split(",")
        else:
            wanted_groups = list(catalog_groups.keys())
        for gid in wanted_groups:
            if gid not in catalog_groups:
                log.warning("Unknown catalog group: %s", gid)
                continue
            flat_name = gid.replace("/", "-")
            work[flat_name] = lambda g=gid: resolve_catalog_group(g, catalog, resolver)

    log.info("Building %d items with %d workers", len(work), args.jobs)

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(build_item, name, fn(), dist, args.dry_run): name
            for name, fn in work.items()
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                log.error("  %s: FAILED — %s", name, e)
                results.append({"name": name, "error": str(e)})

    if not args.dry_run:
        dist.mkdir(parents=True, exist_ok=True)
        meta = {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": {r["name"]: r for r in results},
            "total": len(results),
            "total_rules": sum(r.get("rule_count", 0) for r in results),
        }
        (dist / "build-meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
        )
        log.info("Done: %d items, %d total rules", meta["total"], meta["total_rules"])


if __name__ == "__main__":
    main()
