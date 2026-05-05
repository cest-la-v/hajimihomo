#!/usr/bin/env python3
"""
hajimihomo build orchestrator.

Two build targets:

1. Atomic categories — source/rule/*/sources.yaml (one file per bm7 category)
   Resolved with sub-rule includes/excludes from source/rule/relationships.yaml.

2. Catalog groups    — source/catalog.yaml (semantic bundles for policy groups)
   Each group unions effective_rules of its bm7 members: or other groups
   in members_ref:. IDs use slashes (proxy/google) → flat filenames (proxy-google).

Output per name (Tier 1 always; splits only for classical-behavior categories):
  dist/mihomo/<name>.yaml              — Tier 1: all-in-one (all rule types)
  dist/mihomo/<name>.domain.yaml       — split: DOMAIN + DOMAIN-SUFFIX (behavior:domain)
  dist/mihomo/<name>.ip.yaml           — split: IP-CIDR with no-resolve (behavior:ipcidr)
  dist/mihomo/<name>.ip-resolve.yaml   — split: IP-CIDR without no-resolve (load LAST)
  dist/mihomo/<name>.residual.yaml     — split: DOMAIN-KEYWORD + DOMAIN-REGEX + IP-ASN
  dist/mihomo/<name>.process.yaml      — split: PROCESS-NAME only
  dist/singbox/<name>.json             — Tier 1: all-in-one
  dist/singbox/<name>.domain.json      — split: DOMAIN + DOMAIN-SUFFIX
  dist/singbox/<name>.ip.json          — split: all IP-CIDR (no ip-resolve split for sing-box)
  dist/singbox/<name>.residual.json    — split: DOMAIN-KEYWORD + DOMAIN-REGEX
  dist/singbox/<name>.process.json     — split: PROCESS-NAME only

Do NOT combine the Tier-1 file with splits — rules would be evaluated twice.

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

from convert.parse import fetch_and_parse, parse_lines
from convert.compress import compress
from convert.mihomo import (
    detect_behavior,
    to_yaml as to_mihomo_yaml,
    to_domain_yaml,
    to_ip_yaml,
    to_ip_resolve_yaml,
    to_residual_yaml,
    to_process_yaml,
)
from convert.singbox import (
    to_json as to_singbox_json,
    to_domain_json,
    to_ip_json,
    to_residual_json,
    to_process_json,
)

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
                     ∪ appends[cat]          our custom additions (survive exclusion)
                     - removes[cat]          our explicit removals (always win)

    Results are memoized; thread-safe for parallel builds (last-write-wins on
    cache is safe because results are deterministic).
    """

    def __init__(
        self,
        sources: dict[str, list[str]],
        includes: dict[str, list[str]],
        excludes: dict[str, list[str]],
        appends: dict[str, frozenset[tuple[str, str]]] | None = None,
        removes: dict[str, frozenset[tuple[str, str]]] | None = None,
    ) -> None:
        self._sources = sources
        self._includes = includes
        self._excludes = excludes
        self._appends = appends or {}
        self._removes = removes or {}
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

        # 4. Our custom additions (survive category-level exclusion)
        rules |= self._appends.get(category, frozenset())

        # 5. Our explicit removals (always win, applied last)
        rules -= self._removes.get(category, frozenset())

        result = frozenset(rules)
        with self._lock:
            self._cache[category] = result
        return result


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_all_sources(source_dir: Path) -> tuple[
    dict[str, list[str]],
    dict[str, frozenset[tuple[str, str]]],
    dict[str, frozenset[tuple[str, str]]],
]:
    """
    Discover all categories under source_dir and return:
      sources  — {cat: [url, ...]}          from sources.yaml
      appends  — {cat: frozenset of rules}   from append.list
      removes  — {cat: frozenset of rules}   from remove.list

    A category is discovered if its directory contains any of these files.
    """
    sources: dict[str, list[str]] = {}
    appends: dict[str, frozenset[tuple[str, str]]] = {}
    removes: dict[str, frozenset[tuple[str, str]]] = {}

    for cat_dir in sorted(source_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        category = cat_dir.name

        sources_file = cat_dir / "sources.yaml"
        if sources_file.exists():
            data = yaml.safe_load(sources_file.read_text())
            urls = data.get("sources", [])
            if urls:
                sources[category] = urls

        append_file = cat_dir / "append.list"
        if append_file.exists():
            rules = frozenset(parse_lines(append_file.read_text()))
            if rules:
                appends[category] = rules

        remove_file = cat_dir / "remove.list"
        if remove_file.exists():
            rules = frozenset(parse_lines(remove_file.read_text()))
            if rules:
                removes[category] = rules

    return sources, appends, removes


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

    Supported catalog.yaml fields:
      members:      list of bm7 category names → unioned via RuleResolver
      members_ref:  list of other catalog group IDs → unioned recursively
      excludes:     list of bm7 category names → subtracted from result
      excludes_ref: list of other catalog group IDs → subtracted recursively

    This mirrors the same include/exclude semantics as relationships.yaml
    but expressed directly in catalog YAML for catalog-level composition.
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

    # Union: direct bm7 category members
    for cat in spec.get("members", []):
        rules.update(resolver.effective_rules(cat))

    # Union: references to other catalog groups
    for ref in spec.get("members_ref", []):
        rules.update(resolve_catalog_group(ref, catalog, resolver, new_stack))

    # Subtract: direct bm7 categories
    for cat in spec.get("excludes", []):
        rules -= resolver.effective_rules(cat)

    # Subtract: other catalog groups
    for ref in spec.get("excludes_ref", []):
        rules -= resolve_catalog_group(ref, catalog, resolver, new_stack)

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
    """Compress and emit all outputs for one named rule set."""
    t0 = time.monotonic()
    rules = compress(list(raw_rules))
    behavior = detect_behavior(rules)
    elapsed = time.monotonic() - t0

    # Compute splits — only for classical-behavior categories (pure domain/ipcidr
    # categories already have the right behavior:* in their Tier-1 file)
    mh_splits: dict[str, str] = {}
    sb_splits: dict[str, str] = {}
    if behavior == "classical":
        for split_name, mh_fn, sb_fn in [
            ("domain",     lambda: to_domain_yaml(rules, name),     lambda: to_domain_json(rules, name)),
            ("ip",         lambda: to_ip_yaml(rules, name),          lambda: to_ip_json(rules, name)),
            ("ip-resolve", lambda: to_ip_resolve_yaml(rules, name),  None),
            ("residual",   lambda: to_residual_yaml(rules, name),    lambda: to_residual_json(rules, name)),
            ("process",    lambda: to_process_yaml(rules, name),     lambda: to_process_json(rules, name)),
        ]:
            mh_content = mh_fn()
            if mh_content:
                mh_splits[split_name] = mh_content
            if sb_fn is not None:
                sb_content = sb_fn()
                if sb_content:
                    sb_splits[split_name] = sb_content

    meta = {
        "name": name,
        "rule_count": len(rules),
        "behavior": behavior,
        "elapsed_s": round(elapsed, 2),
        "splits": sorted(set(mh_splits) | set(sb_splits)),
    }

    if dry_run:
        splits_str = ",".join(sorted(set(mh_splits) | set(sb_splits))) or "none"
        log.info("  [dry-run] %s: %d rules (%s) splits=[%s]", name, len(rules), behavior, splits_str)
        return meta

    mihomo_dir = dist / "mihomo"
    singbox_dir = dist / "singbox"
    mihomo_dir.mkdir(parents=True, exist_ok=True)
    singbox_dir.mkdir(parents=True, exist_ok=True)

    (mihomo_dir / f"{name}.yaml").write_text(to_mihomo_yaml(rules, name))
    (singbox_dir / f"{name}.json").write_text(to_singbox_json(rules, name))

    for split_name, content in mh_splits.items():
        (mihomo_dir / f"{name}.{split_name}.yaml").write_text(content)

    for split_name, content in sb_splits.items():
        (singbox_dir / f"{name}.{split_name}.json").write_text(content)

    log.info("  %s: %d rules (%s) splits=[%s] in %.1fs",
             name, len(rules), behavior,
             ",".join(meta["splits"]) or "none",
             elapsed)
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

    all_sources, appends, removes = load_all_sources(source_dir)
    includes_map, excludes_map = load_relationships(source_dir)
    catalog = load_catalog(repo_root / "source" / "catalog.yaml")

    resolver = RuleResolver(all_sources, includes_map, excludes_map, appends, removes)

    # All discovered categories: union of sources, appends, removes keys
    all_categories = set(all_sources) | set(appends) | set(removes)

    # ---- Collect work items: (name, callable_that_returns_frozenset) ----
    # Key: output file stem; value: callable producing raw frozenset of rules
    work: dict[str, any] = {}

    # Build atomics unless --all-groups is set or only --groups were requested
    build_atomics = not args.all_groups and not (args.groups and not args.categories)
    if build_atomics:
        emit_cats = [cat for cat in sorted(all_categories) if cat not in SKIP_CATEGORIES]
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
