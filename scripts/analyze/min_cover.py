#!/usr/bin/env python3
"""
scripts/analyze/min_cover.py

Deep redundancy analysis and minimum-set-cover computation for vendor repos.

For each repo:
  1. Which of its rules are uncovered by ANY other repo (globally unique)?
  2. Are those "globally unique" rules actually covered by some repo-combo?

Then:
  3. Greedy minimum set cover: fewest repos for maximum rule union.
  4. Export rules uncovered by the final cover set to overrides/*.list

Usage:
    python3 scripts/analyze/min_cover.py [--jobs N] [--output-dir DIR] [--exclude owner/repo ...]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

# Reuse all the heavy lifting from vendor_analysis.py
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from vendor_analysis import (
    REPO_ROOT,
    CATS_PATH,
    collect_repo_files,
    git_read,
    parse_rules,
    RuleIndex,
    RepoData,
    Rule,
)

OUTPUT_DIR = REPO_ROOT / "scripts" / "analyze" / "output"


# ---------------------------------------------------------------------------
# Load all repos (same as vendor_analysis main, extracted)
# ---------------------------------------------------------------------------

def load_repos(jobs: int = 8, exclude: set[str] | None = None) -> list[RepoData]:
    exclude = exclude or set()
    print("Loading categories.yaml...")
    cats = yaml.safe_load(CATS_PATH.read_text())
    repo_files = collect_repo_files(cats)
    if exclude:
        for ex in exclude:
            repo_files.pop(ex, None)
        print(f"  Excluded: {', '.join(exclude)}")
    print(f"  {len(repo_files)} repos, "
          f"{sum(len(f) for f in repo_files.values())} unique source files")

    all_keys = [
        (repo_key, ref, path)
        for repo_key, files in repo_files.items()
        for ref, path in files
    ]

    def _load(key):
        owner_repo, ref, path = key
        vendor_dir = REPO_ROOT / "vendor" / owner_repo
        if not vendor_dir.exists():
            return key, RuntimeError(f"vendor/{owner_repo} not cloned")
        try:
            return key, git_read(vendor_dir, ref, path)
        except RuntimeError as e:
            return key, e

    print(f"Loading {len(all_keys)} source files ({jobs} threads)...")
    file_cache: dict[tuple, str | Exception] = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        done = 0
        for key, result in pool.map(_load, all_keys):
            file_cache[key] = result
            done += 1
            if done % 100 == 0 or done == len(all_keys):
                print(f"  {done}/{len(all_keys)}", end="\r")
    print()

    # Aggregate per-repo
    repo_data: dict[str, RepoData] = {}
    for repo_key in repo_files:
        rd = RepoData(name=repo_key)
        seen: set[tuple[str, str]] = set()
        for (ref, path), cats_list in repo_files[repo_key].items():
            raw = file_cache.get((repo_key, ref, path))
            if isinstance(raw, Exception) or raw is None:
                rd.files_failed += 1
                continue
            rd.files_loaded += 1
            for rule in parse_rules(raw):
                key2 = (rule.rtype, rule.value)
                if key2 not in seen:
                    seen.add(key2)
                    rd.rules.append(rule)
                    rd.rule_set.add(key2)
                    rd.index.add(rule)
        repo_data[repo_key] = rd

    repos = list(repo_data.values())
    print(f"Loaded {len(repos)} repos, "
          f"{sum(len(r.rules) for r in repos):,} total rules")
    return repos


# ---------------------------------------------------------------------------
# Global coverage: for each rule, which repos cover it
# ---------------------------------------------------------------------------

def build_global_coverage(
    repos: list[RepoData],
    jobs: int = 8,
) -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str], set[str]]]:
    """
    Returns:
        coverage[key]    = repos that cover rule `key` EXCLUDING its direct owners
        rule_owners[key] = repos that have rule `key` in their exact rule_set

    A rule is "globally unique" when coverage[key] is empty — no other repo
    (beyond those that already own it) covers it via subsumption.
    """
    # 1. Build ownership map: rule_key → set of repos with it in exact rule_set
    rule_owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    for rd in repos:
        for key in rd.rule_set:
            rule_owners[key].add(rd.name)

    # 2. Collect all unique rules (one Rule object per key)
    unique_rules: dict[tuple[str, str], Rule] = {}
    for rd in repos:
        for rule in rd.rules:
            key = (rule.rtype, rule.value)
            if key not in unique_rules:
                unique_rules[key] = rule

    total = len(unique_rules)
    print(f"  {total:,} unique rules across {len(repos)} repos")

    indexed = [(r.name, r.index) for r in repos if r.rules]

    # 3. Parallel coverage check — exclude each rule's owners from coverage
    rule_items = list(unique_rules.items())
    chunk_size = max(1, total // (jobs * 4))
    chunks = [rule_items[i:i + chunk_size] for i in range(0, total, chunk_size)]

    coverage: dict[tuple[str, str], list[str]] = {}
    done = 0

    def _check_chunk(chunk):
        result = {}
        for key, rule in chunk:
            owners = rule_owners[key]
            result[key] = [name for name, idx in indexed
                           if name not in owners and idx.covers(rule)]
        return result

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for partial in pool.map(_check_chunk, chunks):
            coverage.update(partial)
            done += len(partial)
            print(f"  coverage {done:,}/{total:,}", end="\r")

    print(f"  coverage {done:,}/{total:,} done")
    return coverage, dict(rule_owners)


# ---------------------------------------------------------------------------
# Per-repo: globally unique rules (not covered by any other repo)
# ---------------------------------------------------------------------------

def globally_unique_rules(
    rd: RepoData,
    coverage: dict[tuple[str,str], list[str]],
    rule_owners: dict[tuple[str,str], set[str]],
) -> list[Rule]:
    """Rules in rd that no other repo covers (via subsumption or exact match)."""
    return [
        r for r in rd.rules
        if not coverage.get((r.rtype, r.value), [])           # no subsumption cover
        and rule_owners.get((r.rtype, r.value), set()) <= {rd.name}  # no other exact owner
    ]


# ---------------------------------------------------------------------------
# Greedy set cover
# ---------------------------------------------------------------------------

def greedy_set_cover(
    repos: list[RepoData],
    target_rules: set[tuple[str,str]] | None = None,
) -> list[str]:
    """
    Greedy max-coverage selection.
    If target_rules is None, cover all rules across all repos.
    Returns ordered list of repo names (most coverage first).
    """
    if target_rules is None:
        target_rules = set()
        for rd in repos:
            target_rules.update(rd.rule_set)

    uncovered = set(target_rules)
    selected: list[str] = []
    remaining = {rd.name: rd for rd in repos if rd.rules}

    while uncovered and remaining:
        # Pick repo with most uncovered rules
        best_name = max(
            remaining,
            key=lambda n: len(remaining[n].rule_set & uncovered),
        )
        best_rd = remaining.pop(best_name)
        gained = best_rd.rule_set & uncovered
        if not gained:
            break
        uncovered -= gained
        selected.append(best_name)
        print(f"  +{best_name}: +{len(gained):,} rules → {len(uncovered):,} still uncovered")

    return selected


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def fmt_rule(r: Rule) -> str:
    if r.rtype == "DOMAIN":
        return f"DOMAIN,{r.value}"
    if r.rtype == "DOMAIN-SUFFIX":
        return f"DOMAIN-SUFFIX,{r.value}"
    return f"{r.rtype},{r.value}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--output-dir", default="scripts/analyze/output")
    parser.add_argument("--exclude", nargs="*", default=["blackmatrix7/ios_rule_script"],
                        metavar="OWNER/REPO",
                        help="Repos to exclude from analysis (default: blackmatrix7/ios_rule_script)")
    args = parser.parse_args()

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    repos = load_repos(args.jobs, exclude=set(args.exclude))

    # Build global coverage map
    print("\nBuilding global coverage map...")
    coverage, rule_owners = build_global_coverage(repos, jobs=args.jobs)

    total_rules = sum(len(r.rules) for r in repos if r.rules)
    print(f"\nTotal unique rules across all repos: {total_rules:,}")

    # --- Part 1: Per-repo globally-unique analysis ---
    print("\n" + "="*70)
    print("PART 1: Globally-unique rules per repo")
    print("="*70)

    lines: list[str] = [
        "# Vendor Minimum-Cover Analysis",
        "",
        "## Part 1: Globally-Unique Rules Per Repo",
        "",
        "Rules not covered by ANY other vendor repo.",
        "",
        "| Repo | Total Rules | Globally Unique | Unique% |",
        "|---|---:|---:|---:|",
    ]

    unique_per_repo: dict[str, list[Rule]] = {}
    for rd in sorted(repos, key=lambda r: -len(r.rules)):
        if not rd.rules:
            continue
        unique = globally_unique_rules(rd, coverage, rule_owners)
        unique_per_repo[rd.name] = unique
        pct = len(unique) / len(rd.rules)
        lines.append(f"| `{rd.name}` | {len(rd.rules):,} | {len(unique):,} | {pct:.0%} |")
        print(f"  {rd.name}: {len(rd.rules):,} rules, {len(unique):,} globally unique ({pct:.0%})")

    lines += ["", "## Part 2: Redundant Repo Deep-Dive", ""]
    lines += [
        "For the high-redundancy repos (previously flagged), how many of their",
        "'uncovered by primary' rules are covered by ANY other repo?",
        "",
    ]

    # High-redundancy candidates from previous analysis
    HIGH_REDUNDANCY = [
        "geekdada/surge-list",
        "Loyalsoldier/clash-rules",
        "NobyDa/Script",
        "scomper/surge-list",
        "an0na/R",
        "misakaio/chnroutes2",
        "missuo/ASN-China",
        "QiuSimons/Netflix_IP",
    ]

    repo_by_name = {r.name: r for r in repos}

    print("\n" + "="*70)
    print("PART 2: Redundant repo deep-dive")
    print("="*70)

    for rname in HIGH_REDUNDANCY:
        rd = repo_by_name.get(rname)
        if rd is None:
            lines.append(f"### `{rname}` — not in vendor\n")
            continue
        if not rd.rules:
            lines.append(f"### `{rname}` — 0 rules parsed\n")
            continue

        unique = unique_per_repo[rname]
        n = len(rd.rules)
        u = len(unique)
        pct = u / n

        lines += [
            f"### `{rname}`",
            "",
            f"- Total rules: {n:,}",
            f"- Globally unique (no other repo covers them): {u:,} ({pct:.1%})",
            "",
        ]
        print(f"\n{rname}: {n:,} rules, {u:,} globally unique ({pct:.1%})")

        if unique:
            # Show top 20 unique rules
            lines += ["<details><summary>Sample globally-unique rules</summary>", "", "```"]
            for rule in unique[:30]:
                lines.append(fmt_rule(rule))
            if len(unique) > 30:
                lines.append(f"... and {len(unique)-30} more")
            lines += ["```", "</details>", ""]
            print(f"  Sample: {', '.join(fmt_rule(r) for r in unique[:5])}")
        else:
            lines += ["✅ All rules covered by other repos — safe to drop.\n"]
            print("  → All covered, safe to drop")

    # --- Part 3: Greedy minimum set cover ---
    print("\n" + "="*70)
    print("PART 3: Greedy minimum set cover")
    print("="*70)

    # All unique rules we want to cover
    all_target = set()
    for rd in repos:
        all_target.update(rd.rule_set)

    print(f"\nTarget: cover {len(all_target):,} unique rules")
    print("Greedy selection:")

    selected = greedy_set_cover(repos)

    # Compute coverage achieved
    covered = set()
    for name in selected:
        covered.update(repo_by_name[name].rule_set)
    uncovered_final = all_target - covered

    print(f"\nResult: {len(selected)} repos cover "
          f"{len(covered):,}/{len(all_target):,} rules "
          f"({len(covered)/len(all_target):.1%})")

    lines += [
        "## Part 3: Greedy Minimum Set Cover",
        "",
        f"Target: {len(all_target):,} unique rules across all repos.",
        "",
        f"**{len(selected)} repos** cover **{len(covered):,}/{len(all_target):,}** rules "
        f"({len(covered)/len(all_target):.1%}).",
        "",
        "| # | Repo | Rules | Cumulative Coverage |",
        "|---|---|---:|---:|",
    ]

    cumulative = set()
    for i, name in enumerate(selected, 1):
        rd = repo_by_name[name]
        gained = rd.rule_set - cumulative
        cumulative |= rd.rule_set
        pct = len(cumulative) / len(all_target)
        lines.append(f"| {i} | `{name}` | +{len(gained):,} | {pct:.1%} |")

    lines += [
        "",
        f"**Uncovered by any repo:** {len(uncovered_final):,} rules",
        "",
    ]

    # --- Part 4: Export uncovered rules ---
    if uncovered_final:
        overrides_dir = out_dir / "orphan_rules"
        overrides_dir.mkdir(exist_ok=True)

        # Group by which repo they came from
        orphan_by_repo: dict[str, list[Rule]] = defaultdict(list)
        for rd in repos:
            for rule in rd.rules:
                key = (rule.rtype, rule.value)
                if key in uncovered_final:
                    orphan_by_repo[rd.name].append(rule)

        lines += ["## Part 4: Orphan Rules (Uncovered by Any Repo)", ""]
        lines += [
            "These rules appear in only one repo and would be lost if that repo were dropped.",
            "",
            "| Repo | Orphan Rules |",
            "|---|---:|",
        ]
        for rname in sorted(orphan_by_repo, key=lambda n: -len(orphan_by_repo[n])):
            rules = orphan_by_repo[rname]
            lines.append(f"| `{rname}` | {len(rules):,} |")

            # Write export file
            safe = rname.replace("/", "__")
            out_f = overrides_dir / f"{safe}.list"
            out_f.write_text(
                f"# Orphan rules from {rname}\n"
                + "# These rules are NOT covered by any other vendor repo.\n\n"
                + "\n".join(fmt_rule(r) for r in sorted(rules, key=lambda r: (r.rtype, r.value)))
                + "\n"
            )

        lines += ["", f"Exported to `{overrides_dir.relative_to(REPO_ROOT)}/`", ""]
        print(f"\nExported orphan rules to {overrides_dir}/")

    # --- Write report ---
    out_path = out_dir / "min_cover.md"
    out_path.write_text("\n".join(lines))
    print(f"\nReport → {out_path}")


if __name__ == "__main__":
    main()
