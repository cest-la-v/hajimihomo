#!/usr/bin/env python3
"""
Check if rules in downloaded dead-URL candidate files are covered
by our existing vendor repos (excluding blackmatrix7).

Usage:
    python3 scripts/analyze/check_dead_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# reuse parse_rules, RuleIndex from vendor_analysis
sys.path.insert(0, str(Path(__file__).parent))
from vendor_analysis import parse_rules, RuleIndex, Rule, git_read, collect_repo_files

import yaml

REPO_ROOT     = Path(__file__).parent.parent.parent
CATS_PATH     = REPO_ROOT / "source" / "categories.yaml"
VENDOR_DIR    = REPO_ROOT / "vendor"
CANDIDATES    = Path(__file__).parent / "dead_url_candidates"

EXCLUDE_REPOS = {"blackmatrix7/ios_rule_script"}


def load_candidate_files() -> dict[str, list[Rule]]:
    """Load each downloaded candidate yaml and return {filename_stem: [rules]}."""
    result = {}
    for f in sorted(CANDIDATES.glob("*.yaml")):
        rules = parse_rules(f.read_text(encoding="utf-8"))
        result[f.stem] = rules
        print(f"  candidate {f.name}: {len(rules)} rules")
    return result


def build_vendor_indices(cats: dict) -> dict[str, RuleIndex]:
    """Build a RuleIndex per vendor repo (excluding BM7)."""
    from collections import defaultdict
    repo_files = collect_repo_files(cats)

    indices: dict[str, RuleIndex] = {}
    for repo_key, files in sorted(repo_files.items()):
        if repo_key in EXCLUDE_REPOS:
            continue
        vendor_path = VENDOR_DIR / repo_key.replace("/", "/", 1)
        if not vendor_path.exists():
            continue

        idx = RuleIndex()
        loaded = 0
        for (ref, path), _ in files.items():
            try:
                raw = git_read(vendor_path, ref, path)
                for rule in parse_rules(raw):
                    idx.add(rule)
                loaded += 1
            except Exception:
                pass

        if loaded > 0:
            indices[repo_key] = idx
            total = len(idx.domains) + len(idx.suffixes) + len(idx.cidr_exact)
            print(f"  indexed {repo_key}: {total} unique rules")

    return indices


def check_coverage(
    candidates: dict[str, list[Rule]],
    indices: dict[str, RuleIndex],
) -> None:
    print("\n" + "=" * 72)
    print(f"{'FILE':<30}  {'RULES':>5}  {'COVERED BY'}")
    print("=" * 72)

    for stem, rules in sorted(candidates.items()):
        if not rules:
            print(f"{stem:<30}  {'0':>5}  (empty)")
            continue

        covering_repos: list[tuple[str, int]] = []
        for repo, idx in indices.items():
            covered = sum(1 for r in rules if idx.covers(r))
            if covered > 0:
                covering_repos.append((repo, covered))

        covering_repos.sort(key=lambda x: -x[1])

        total = len(rules)
        if covering_repos:
            best_n = covering_repos[0][1]
            best_pct = best_n / total * 100
            coverage_str = ", ".join(
                f"{r} ({n}/{total} = {n/total*100:.0f}%)"
                for r, n in covering_repos[:5]
            )
            flag = "✅ fully" if best_pct == 100 else f"⚠️  {best_pct:.0f}%"
            print(f"{stem:<30}  {total:>5}  {flag} covered")
            for repo, n in covering_repos[:5]:
                pct = n / total * 100
                print(f"  {'':30}          [{repo}: {n}/{total} = {pct:.0f}%]")
        else:
            print(f"{stem:<30}  {total:>5}  ❌ NOT covered by any vendor")
            for r in rules:
                print(f"  {'':30}          rule: {r.rtype},{r.value}")

    print("=" * 72)


def main() -> None:
    print("Loading candidate files...")
    candidates = load_candidate_files()

    print(f"\nLoading vendor indices (excluding {EXCLUDE_REPOS})...")
    cats = yaml.safe_load(CATS_PATH.read_text())
    indices = build_vendor_indices(cats)

    print(f"\n{len(indices)} vendor repos indexed, checking {len(candidates)} candidate files...")
    check_coverage(candidates, indices)


if __name__ == "__main__":
    main()
