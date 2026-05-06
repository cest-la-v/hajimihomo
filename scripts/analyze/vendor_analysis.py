#!/usr/bin/env python3
"""
scripts/analyze/vendor_analysis.py

Analyzes all vendor repos referenced in source/categories.yaml:

  1. Coverage/overlap matrix  — pairwise % of repo A's rules subsumed by repo B
  2. Dependency graph         — DOT output; edge A→B when B covers A above threshold
  3. Curation score           — per-repo metrics to distinguish hand-maintained vs
                                auto-generated repos

Requires all repos to be locally cloned:
    make vendor-sync

Does NOT fall back to HTTP; fails fast on missing repos so results are reproducible.

Supported rule types for overlap analysis:
    DOMAIN, DOMAIN-SUFFIX, IP-CIDR, IP-CIDR6
(KEYWORD, REGEX, PROCESS-NAME, IP-ASN are counted but excluded from subsumption.)

Usage:
    python3 scripts/analyze/vendor_analysis.py [options]

    --output-dir DIR     directory for output files (default: scripts/analyze/output/)
    --edge-pct N         min % coverage for a dependency edge (default: 50)
    --edge-min N         min absolute rules covered for an edge (default: 50)
    --jobs N             parallel file-loading threads (default: 8)
    --no-matrix          skip the full N×N matrix (fast mode)
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
CATS_PATH = REPO_ROOT / "source" / "categories.yaml"

# ---------------------------------------------------------------------------
# Rule model (only comparable types go into overlap analysis)
# ---------------------------------------------------------------------------

OVERLAP_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "IP-CIDR", "IP-CIDR6"}
OTHER_TYPES   = {"DOMAIN-KEYWORD", "DOMAIN-REGEX", "PROCESS-NAME", "IP-ASN", "IP-CIDR6"}


class Rule(NamedTuple):
    rtype: str
    value: str


# ---------------------------------------------------------------------------
# Local git reader — strict (no HTTP fallback)
# ---------------------------------------------------------------------------

def git_read(vendor_dir: Path, ref: str, path: str) -> str:
    """
    Read a file from a local vendor clone.

    Fast path: read directly from the working tree (works for --depth=1 clones,
    no subprocess needed). Fallback: git-show for edge cases.
    Raises RuntimeError if the file cannot be found.
    """
    import urllib.parse
    path = urllib.parse.unquote(path)

    # Fast path: filesystem read from working tree
    file_path = vendor_dir / path
    if file_path.exists():
        return file_path.read_text(encoding="utf-8", errors="replace")

    # Fallback: git-show (handles non-checked-out refs)
    for git_ref in (ref, f"origin/{ref}", "origin/HEAD"):
        r = subprocess.run(
            ["git", "show", f"{git_ref}:{path}"],
            cwd=vendor_dir,
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return r.stdout
    raise RuntimeError(
        f"Cannot resolve {ref}:{path} in {vendor_dir} — run 'make vendor-sync'"
    )


# ---------------------------------------------------------------------------
# Text-level heuristics (computed BEFORE parsing — preserves comments)
# ---------------------------------------------------------------------------

@dataclass
class TextMetrics:
    total_lines: int = 0
    comment_lines: int = 0        # lines starting with # or //
    blank_lines: int = 0
    keyword_rules: int = 0        # DOMAIN-KEYWORD lines
    regex_rules: int = 0          # DOMAIN-REGEX lines
    process_rules: int = 0        # PROCESS-NAME lines
    asn_rules: int = 0            # IP-ASN lines
    has_header: bool = False      # first non-blank line is a comment
    distinct_prefixes: set[str] = field(default_factory=set)  # rule type prefixes

    def comment_density(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return self.comment_lines / self.total_lines

    def exotic_rule_count(self) -> int:
        return self.keyword_rules + self.regex_rules + self.process_rules + self.asn_rules


_CLASH_TYPE_RE = re.compile(r"^([A-Z][A-Z0-9\-]+),", re.IGNORECASE)


def analyse_text(raw: str) -> TextMetrics:
    m = TextMetrics()
    first_content = True
    for line in raw.splitlines():
        m.total_lines += 1
        stripped = line.strip()
        if not stripped:
            m.blank_lines += 1
            continue
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("!"):
            m.comment_lines += 1
            if first_content:
                m.has_header = True
        else:
            first_content = False
            upper = stripped.upper()
            if upper.startswith("DOMAIN-KEYWORD,"):
                m.keyword_rules += 1
            elif upper.startswith("DOMAIN-REGEX,"):
                m.regex_rules += 1
            elif upper.startswith("PROCESS-NAME,"):
                m.process_rules += 1
            elif upper.startswith("IP-ASN,"):
                m.asn_rules += 1
            hit = _CLASH_TYPE_RE.match(stripped)
            if hit:
                m.distinct_prefixes.add(hit.group(1).upper())
    return m


# ---------------------------------------------------------------------------
# Rule parser — produces only OVERLAP_TYPES rules
# ---------------------------------------------------------------------------

_CIDR4_RE  = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")
_CIDR6_RE  = re.compile(r"^[0-9a-fA-F:]+:[0-9a-fA-F:]*/\d{1,3}$")
_DOMAIN_RE = re.compile(r"^(?!\-)([a-zA-Z0-9\-_]+\.)+[a-zA-Z]{2,}$")


def parse_rules(raw: str) -> list[Rule]:
    rules: list[Rule] = []
    in_payload = False
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//") or line.startswith("!"):
            continue
        if line == "payload:":
            in_payload = True
            continue
        if in_payload and not line.startswith("-"):
            in_payload = False
        if line.startswith("- "):
            line = line[2:]
        # '+.domain' (quoted, Loyalsoldier style) or +.domain (unquoted, sub-store style)
        if line.startswith("'+.") and line.endswith("'"):
            rules.append(Rule("DOMAIN-SUFFIX", line[3:-1].lower()))
            continue
        if line.startswith("+.") and _DOMAIN_RE.match(line[2:]):
            rules.append(Rule("DOMAIN-SUFFIX", line[2:].lower()))
            continue
        if line.startswith("'") and line.endswith("'"):
            line = line[1:-1]
        if line.startswith(".") and _DOMAIN_RE.match(line[1:]):
            rules.append(Rule("DOMAIN-SUFFIX", line[1:].lower()))
            continue
        if "," in line:
            parts = line.split(",", 2)
            rtype = parts[0].strip().upper()
            value = parts[1].strip().lower()
            if rtype in ("DOMAIN", "DOMAIN-SUFFIX"):
                rules.append(Rule(rtype, value))
            elif rtype in ("IP-CIDR", "IP-CIDR6", "IP6-CIDR"):
                rules.append(Rule("IP-CIDR6" if ":" in value else "IP-CIDR", value))
            continue
        if _CIDR4_RE.match(line):
            rules.append(Rule("IP-CIDR", line))
        elif _CIDR6_RE.match(line):
            rules.append(Rule("IP-CIDR6", line))
        elif _DOMAIN_RE.match(line):
            rules.append(Rule("DOMAIN-SUFFIX", line.lower()))
    return rules


# ---------------------------------------------------------------------------
# Domain+CIDR index for fast subsumption
# ---------------------------------------------------------------------------

@dataclass
class RuleIndex:
    domains:     set[str] = field(default_factory=set)
    suffixes:    set[str] = field(default_factory=set)
    cidr_exact:  set[str] = field(default_factory=set)   # normalised CIDR strings, exact-match only

    def add(self, rule: Rule) -> None:
        if rule.rtype == "DOMAIN":
            self.domains.add(rule.value)
        elif rule.rtype == "DOMAIN-SUFFIX":
            self.suffixes.add(rule.value)
        elif rule.rtype in ("IP-CIDR", "IP-CIDR6"):
            try:
                self.cidr_exact.add(
                    str(ipaddress.ip_network(rule.value, strict=False))
                )
            except ValueError:
                pass

    def finalise(self) -> None:
        pass  # no-op; kept for call-site compatibility

    def covers(self, rule: Rule) -> bool:
        """
        Domain rules: subsumption (suffix hierarchy) — O(depth) hash lookups.
        CIDR rules:   exact match only — O(1).  Subsumption is too slow at scale.
        """
        if rule.rtype in ("DOMAIN", "DOMAIN-SUFFIX"):
            v = rule.value
            if v in self.domains:
                return True
            parts = v.split(".")
            for i in range(len(parts)):
                if ".".join(parts[i:]) in self.suffixes:
                    return True
            return False
        if rule.rtype in ("IP-CIDR", "IP-CIDR6"):
            try:
                norm = str(ipaddress.ip_network(rule.value, strict=False))
                return norm in self.cidr_exact
            except (ValueError, TypeError):
                return False
        return False


# ---------------------------------------------------------------------------
# Per-repo data
# ---------------------------------------------------------------------------

@dataclass
class RepoData:
    name: str                                         # "owner/repo"
    files_loaded: int = 0
    files_failed: int = 0
    raw_rule_count: int = 0                           # before dedup
    rules: list[Rule] = field(default_factory=list)  # deduped OVERLAP_TYPES
    rule_set: set[tuple[str,str]] = field(default_factory=set)
    index: RuleIndex = field(default_factory=RuleIndex)
    text_metrics: TextMetrics = field(default_factory=TextMetrics)
    ref_used: str = ""


# ---------------------------------------------------------------------------
# Load categories.yaml → per-repo file list
# ---------------------------------------------------------------------------

def collect_repo_files(cats: dict) -> dict[str, dict[tuple[str,str,str], list[str]]]:
    """
    Returns {owner/repo -> {(ref, path) -> [category_keys]}}
    """
    result: dict[str, dict[tuple[str,str,str], list[str]]] = defaultdict(lambda: defaultdict(list))
    for key, cat in cats.items():
        for src in cat.get("sources", []):
            if not src.startswith("repo:"):
                continue
            parts = src[5:].split("/", 3)
            if len(parts) < 4:
                continue
            owner, repo, ref, path = parts
            repo_key = f"{owner}/{repo}"
            result[repo_key][(ref, path)].append(str(key))
    return result


# ---------------------------------------------------------------------------
# Curation scoring
# ---------------------------------------------------------------------------

CURATION_LABELS = ["likely auto-generated", "mixed", "likely curated"]


def build_global_rule_counts(repos: list[RepoData]) -> dict[tuple[str,str], int]:
    """Count how many repos contain each (rtype, value) rule — O(total_rules)."""
    counts: dict[tuple[str,str], int] = {}
    for rd in repos:
        for key in rd.rule_set:
            counts[key] = counts.get(key, 0) + 1
    return counts


def curation_score(rd: RepoData, global_counts: dict[tuple[str,str], int]) -> dict:
    """
    Returns a dict of component metrics + final label.
    Uses exact-match uniqueness (O(n)) via pre-built global_counts.
    Higher score = more curated.
    """
    n = len(rd.rules)
    score = 0

    # 1. Size: small repos are usually curated
    size_pts = 3 if n < 200 else 2 if n < 1000 else 1 if n < 10_000 else 0
    score += size_pts

    # 2. Comment density
    cd = rd.text_metrics.comment_density()
    cd_pts = 2 if cd > 0.10 else 1 if cd > 0.02 else 0
    score += cd_pts

    # 3. Exotic rules (KEYWORD, REGEX, PROCESS-NAME, ASN) → hand-curated signal
    exotic = rd.text_metrics.exotic_rule_count()
    exotic_pts = 2 if exotic > 20 else 1 if exotic > 0 else 0
    score += exotic_pts

    # 4. Type diversity
    diversity = len(rd.text_metrics.distinct_prefixes)
    div_pts = 2 if diversity >= 4 else 1 if diversity >= 2 else 0
    score += div_pts

    # 5. Exact-match uniqueness: rules appearing in only this repo (O(n) hash lookup)
    unique = sum(1 for key in rd.rule_set if global_counts.get(key, 0) == 1)
    unique_ratio = unique / n if n else 0
    uniq_pts = 3 if unique_ratio > 0.5 else 2 if unique_ratio > 0.2 else 1 if unique_ratio > 0.05 else 0
    score += uniq_pts

    max_score = 12
    label_idx = 0 if score < 4 else 2 if score >= 8 else 1

    return {
        "total_rules": n,
        "unique_rules": unique,
        "unique_ratio": unique_ratio,
        "comment_density": cd,
        "exotic_rules": exotic,
        "type_diversity": diversity,
        "score": score,
        "max_score": max_score,
        "label": CURATION_LABELS[label_idx],
    }


# ---------------------------------------------------------------------------
# Coverage matrix
# ---------------------------------------------------------------------------

def compute_coverage(repos: list[RepoData], jobs: int = 4) -> dict[str, dict[str, float]]:
    """
    Returns matrix[A][B] = fraction of A's rules covered by B's index.
    Rows computed in parallel; zero-rule repos get all-zero rows.
    """
    active = [r for r in repos if r.rules]

    def _row(a: RepoData) -> tuple[str, dict[str, float]]:
        n = len(a.rules)
        row: dict[str, float] = {}
        for b in repos:
            if a.name == b.name:
                row[b.name] = 1.0
            elif not b.rules:
                row[b.name] = 0.0
            else:
                covered = sum(1 for r in a.rules if b.index.covers(r))
                row[b.name] = covered / n
        return a.name, row

    matrix: dict[str, dict[str, float]] = {
        r.name: {b.name: (1.0 if r.name == b.name else 0.0) for b in repos}
        for r in repos if not r.rules
    }
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        done = 0
        for name, row in pool.map(_row, active):
            matrix[name] = row
            done += 1
            print(f"  matrix {done}/{len(active)}", end="\r")
    print()
    return matrix


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def short_name(full: str) -> str:
    return full.split("/")[-1]


def write_dot(repos: list[RepoData], matrix: dict, edge_pct: float, edge_min: int,
              out_path: Path) -> int:
    lines = ["digraph vendor_deps {", '  rankdir=LR;', '  node [shape=box fontname="monospace" fontsize=10];']
    edge_count = 0
    for a in repos:
        na = len(a.rules)
        label = f"{short_name(a.name)}\\n{na:,} rules"
        lines.append(f'  "{a.name}" [label="{label}"];')
    for a in repos:
        na = len(a.rules)
        if na == 0:
            continue
        for b in repos:
            if a.name == b.name:
                continue
            frac = matrix[a.name][b.name]
            covered = int(frac * na)
            if frac >= edge_pct / 100 and covered >= edge_min:
                pct = int(frac * 100)
                lines.append(f'  "{a.name}" -> "{b.name}" [label="{pct}%" weight={pct}];')
                edge_count += 1
    lines.append("}")
    out_path.write_text("\n".join(lines))
    return edge_count


def write_report(repos: list[RepoData], matrix: dict, curation: dict[str, dict],
                 edge_pct: float, edge_min: int, out_path: Path) -> None:
    lines: list[str] = []

    lines += [
        "# Vendor Repo Analysis Report",
        "",
        f"Analysed **{len(repos)}** vendor repos referenced in `source/categories.yaml`.",
        "",
    ]

    # --- Repo summary table ---
    lines += [
        "## Repo Summary",
        "",
        "| Repo | Rules | Unique | Unique% | Comments% | Exotic | Types | Score | Label |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rd in sorted(repos, key=lambda r: -len(r.rules)):
        c = curation[rd.name]
        lines.append(
            f"| `{rd.name}` | {c['total_rules']:,} | {c['unique_rules']:,} | "
            f"{c['unique_ratio']:.0%} | {c['comment_density']:.0%} | {c['exotic_rules']} | "
            f"{c['type_diversity']} | {c['score']}/{c['max_score']} | {c['label']} |"
        )
    lines.append("")

    # --- Coverage matrix (condensed: only rows with ≥1 edge) ---
    lines += [
        "## Coverage Matrix",
        "",
        f"_Cell = % of **row** repo's rules subsumed by **column** repo._  "
        f"Only repos with ≥1 strong edge (≥{int(edge_pct)}%, ≥{edge_min} rules) shown.",
        "",
    ]
    # find repos that appear in at least one edge
    active = set()
    for a in repos:
        na = len(a.rules)
        if na == 0:
            continue
        for b in repos:
            if a.name == b.name:
                continue
            frac = matrix[a.name][b.name]
            if frac >= edge_pct / 100 and int(frac * na) >= edge_min:
                active.add(a.name)
                active.add(b.name)
    active_repos = [r for r in repos if r.name in active]

    if active_repos:
        col_names = [short_name(r.name) for r in active_repos]
        lines.append("| Repo \\ Covered by | " + " | ".join(col_names) + " |")
        lines.append("|---|" + "---|" * len(active_repos))
        for a in active_repos:
            na = len(a.rules)
            cells = []
            for b in active_repos:
                if a.name == b.name:
                    cells.append(" — ")
                elif na == 0:
                    cells.append("N/A")
                else:
                    pct = matrix[a.name][b.name]
                    cells.append(f"{pct:.0%}")
            lines.append(f"| `{short_name(a.name)}` | " + " | ".join(cells) + " |")
        lines.append("")
    else:
        lines += ["_(no strong edges found — try lowering --edge-pct)_", ""]

    # --- Full matrix appendix ---
    lines += [
        "## Full Coverage Matrix (all repos)",
        "",
        "| Repo | " + " | ".join(short_name(r.name) for r in repos) + " |",
        "|---|" + "---|" * len(repos),
    ]
    for a in repos:
        na = len(a.rules)
        cells = []
        for b in repos:
            if a.name == b.name:
                cells.append("—")
            elif na == 0:
                cells.append("N/A")
            else:
                pct = matrix[a.name][b.name]
                cells.append(f"{pct:.0%}" if pct >= 0.01 else "0%")
        lines.append(f"| `{short_name(a.name)}` | " + " | ".join(cells) + " |")
    lines.append("")

    # --- Dependency narrative ---
    lines += ["## Dependency Graph Edges", ""]
    lines += [f"Edges where B covers ≥{int(edge_pct)}% of A and ≥{edge_min} absolute rules.", ""]
    for a in repos:
        na = len(a.rules)
        if na == 0:
            continue
        deps = []
        for b in repos:
            if a.name == b.name:
                continue
            frac = matrix[a.name][b.name]
            covered = int(frac * na)
            if frac >= edge_pct / 100 and covered >= edge_min:
                deps.append((b.name, frac, covered))
        if deps:
            deps.sort(key=lambda x: -x[1])
            for bname, frac, covered in deps:
                lines.append(
                    f"- `{a.name}` → `{bname}`: {frac:.0%} ({covered:,}/{na:,} rules covered)"
                )
    lines.append("")

    out_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="scripts/analyze/output")
    parser.add_argument("--edge-pct", type=float, default=50.0)
    parser.add_argument("--edge-min", type=int, default=50)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--no-matrix", action="store_true")
    args = parser.parse_args()

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading categories.yaml...")
    cats = yaml.safe_load(CATS_PATH.read_text())
    repo_files = collect_repo_files(cats)
    print(f"Found {len(repo_files)} repos, "
          f"{sum(len(f) for f in repo_files.values())} unique source files")

    # --- Load all files in parallel ---
    # Map (owner/repo, ref, path) → raw text
    print(f"\nLoading source files ({args.jobs} threads)...")
    file_cache: dict[tuple[str,str,str], str | Exception] = {}

    def _load(key: tuple[str,str,str]) -> tuple[tuple[str,str,str], str | Exception]:
        owner_repo, ref, path = key
        vendor_dir = REPO_ROOT / "vendor" / owner_repo
        if not vendor_dir.exists():
            return key, RuntimeError(f"vendor/{owner_repo} not cloned")
        try:
            return key, git_read(vendor_dir, ref, path)
        except RuntimeError as e:
            return key, e

    all_keys = [
        (repo_key, ref, path)
        for repo_key, files in repo_files.items()
        for ref, path in files
    ]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(_load, k): k for k in all_keys}
        done = 0
        for future in as_completed(futures):
            key, result = future.result()
            file_cache[key] = result
            done += 1
            if done % 100 == 0 or done == len(all_keys):
                print(f"  {done}/{len(all_keys)} files loaded", end="\r")
    print()

    # --- Build per-repo data ---
    print("\nBuilding per-repo rule sets...")
    repos: list[RepoData] = []
    failed_repos: list[str] = []

    for repo_key, files in sorted(repo_files.items()):
        rd = RepoData(name=repo_key)
        combined_text_lines: list[str] = []

        for (ref, path), _ in files.items():
            cache_key = (repo_key, ref, path)
            result = file_cache.get(cache_key)
            if result is None or isinstance(result, Exception):
                rd.files_failed += 1
                if isinstance(result, Exception):
                    print(f"  WARN {repo_key}:{ref}:{path} — {result}", file=sys.stderr)
                continue
            rd.files_loaded += 1
            combined_text_lines.append(result)

        if rd.files_loaded == 0:
            print(f"  SKIP {repo_key} — no files loaded", file=sys.stderr)
            failed_repos.append(repo_key)
            continue

        combined = "\n".join(combined_text_lines)

        # text metrics (before parse strips comments)
        for raw_text in combined_text_lines:
            tm = analyse_text(raw_text)
            rd.text_metrics.total_lines  += tm.total_lines
            rd.text_metrics.comment_lines += tm.comment_lines
            rd.text_metrics.blank_lines   += tm.blank_lines
            rd.text_metrics.keyword_rules += tm.keyword_rules
            rd.text_metrics.regex_rules   += tm.regex_rules
            rd.text_metrics.process_rules += tm.process_rules
            rd.text_metrics.asn_rules     += tm.asn_rules
            rd.text_metrics.distinct_prefixes |= tm.distinct_prefixes
            if tm.has_header:
                rd.text_metrics.has_header = True

        # parse rules — dedup
        all_parsed = parse_rules(combined)
        rd.raw_rule_count = len(all_parsed)
        seen: set[tuple[str,str]] = set()
        for rule in all_parsed:
            if rule.rtype not in OVERLAP_TYPES:
                continue
            key_t = (rule.rtype, rule.value)
            if key_t not in seen:
                seen.add(key_t)
                rd.rules.append(rule)
                rd.rule_set.add(key_t)
                rd.index.add(rule)

        repos.append(rd)
        rd.index.finalise()
        print(f"  {repo_key:<45} {len(rd.rules):>7,} rules  "
              f"({rd.files_loaded} files, {rd.files_failed} failed)")

    print(f"\nLoaded {len(repos)} repos, {len(failed_repos)} failed")

    if args.no_matrix:
        print("--no-matrix: skipping coverage matrix")
        matrix: dict = {r.name: {r2.name: 1.0 if r.name == r2.name else 0.0
                                   for r2 in repos} for r in repos}
    else:
        print(f"\nComputing {len(repos)}×{len(repos)} coverage matrix ({args.jobs} threads)...")
        matrix = compute_coverage(repos, jobs=args.jobs)
        print("Matrix done.")

    # --- Curation scores ---
    print("\nComputing curation scores...")
    global_counts = build_global_rule_counts(repos)
    curation: dict[str, dict] = {}
    for rd in repos:
        curation[rd.name] = curation_score(rd, global_counts)

    # --- Outputs ---
    report_path = out_dir / "vendor_analysis.md"
    dot_path    = out_dir / "vendor_graph.dot"

    write_report(repos, matrix, curation, args.edge_pct, args.edge_min, report_path)
    edge_count = write_dot(repos, matrix, args.edge_pct, args.edge_min, dot_path)

    print(f"\nOutputs written to {out_dir}/")
    print(f"  vendor_analysis.md  — full report")
    print(f"  vendor_graph.dot    — {edge_count} dependency edges "
          f"(threshold: ≥{int(args.edge_pct)}%, ≥{args.edge_min} rules)")
    print()
    print("To render the graph (requires graphviz):")
    print(f"  dot -Tsvg {dot_path} -o {out_dir}/vendor_graph.svg")
    print(f"  dot -Tpng {dot_path} -o {out_dir}/vendor_graph.png")


if __name__ == "__main__":
    main()
