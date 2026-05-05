#!/usr/bin/env python3
"""
Vendor corpus coverage validator.

Loads rule files from vendor git branches, then reports:
  1. Coverage matrix: % of each corpus's rules subsumed by each other corpus
  2. Novel rules: rules in a corpus not subsumed by any other corpus combined
  3. Category wiring gaps: 666OS files not referenced in source/categories.yaml

Rule subsumption:
  DOMAIN d is covered by index I if d ∈ I.domains, or any parent suffix of d ∈ I.suffixes
  DOMAIN-SUFFIX s is covered if s ∈ I.suffixes, or any parent suffix of s ∈ I.suffixes
  IP-CIDR c is covered if c is contained by any network in I.cidrs

Usage:
    python scripts/validate/coverage.py [--output report.md] [--novel-cap N]
"""

import argparse
import base64
import ipaddress
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Rule types
# ---------------------------------------------------------------------------

class Rule(NamedTuple):
    rtype: str   # DOMAIN, DOMAIN-SUFFIX, IP-CIDR, IP-CIDR6
    value: str


# ---------------------------------------------------------------------------
# Corpus definitions
# ---------------------------------------------------------------------------

@dataclass
class CorpusDef:
    name: str
    repo: str           # relative to REPO_ROOT
    branch: str         # git ref, e.g. "origin/release"
    files: list[str]    # explicit file paths or globs (resolved via git ls-tree)
    fmt: str = "clash"  # "clash" | "bare" | "gfwlist"


CORPORA: list[CorpusDef] = [
    CorpusDef(
        name="gfwlist",
        repo="vendor/gfwlist/gfwlist",
        branch="HEAD",
        files=["gfwlist.txt"],
        fmt="gfwlist",
    ),
    CorpusDef(
        name="loyalsoldier-gfw",
        repo="vendor/Loyalsoldier/v2ray-rules-dat",
        branch="origin/release",
        files=["gfw.txt"],
        fmt="bare",
    ),
    CorpusDef(
        name="loyalsoldier-direct",
        repo="vendor/Loyalsoldier/v2ray-rules-dat",
        branch="origin/release",
        files=["direct-list.txt"],
        fmt="bare",
    ),
    CorpusDef(
        name="loyalsoldier-google-cn",
        repo="vendor/Loyalsoldier/v2ray-rules-dat",
        branch="origin/release",
        files=["google-cn.txt"],
        fmt="bare",
    ),
    CorpusDef(
        name="dustinwin-cn",
        repo="vendor/DustinWin/domain-list-custom",
        branch="origin/domains",
        files=["cn.list"],
        fmt="clash",
    ),
    CorpusDef(
        name="dustinwin-apple-cn",
        repo="vendor/DustinWin/domain-list-custom",
        branch="origin/domains",
        files=["apple-cn.list"],
        fmt="clash",
    ),
    CorpusDef(
        name="dustinwin-microsoft-cn",
        repo="vendor/DustinWin/domain-list-custom",
        branch="origin/domains",
        files=["microsoft-cn.list"],
        fmt="clash",
    ),
    CorpusDef(
        name="dustinwin-google-cn",
        repo="vendor/DustinWin/domain-list-custom",
        branch="origin/domains",
        files=["google-cn.list"],
        fmt="clash",
    ),
    CorpusDef(
        name="666os-release",
        repo="vendor/666OS/rules",
        branch="origin/release",
        files=["__all_mihomo__"],  # special: all mihomo/*.txt
        fmt="clash",
    ),
    CorpusDef(
        name="our-china",
        repo=".",
        branch="HEAD",
        files=["dist/mihomo/direct-cn.domain.yaml"],
        fmt="clash",
    ),
    CorpusDef(
        name="our-advertising",
        repo=".",
        branch="HEAD",
        files=["dist/mihomo/Advertising.domain.yaml",
               "dist/mihomo/AdvertisingLite.domain.yaml"],
        fmt="clash",
    ),
]


# ---------------------------------------------------------------------------
# Git file reader
# ---------------------------------------------------------------------------

def git_show(repo_path: Path, ref: str, filepath: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{filepath}"],
        cwd=repo_path,
        capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else None


def git_ls_tree(repo_path: Path, ref: str, prefix: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, prefix],
        cwd=repo_path,
        capture_output=True, text=True,
    )
    return [l.strip() for l in result.stdout.splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_CIDR4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")
_CIDR6_RE = re.compile(r"^[0-9a-fA-F:]+/\d{1,3}$")
_DOMAIN_RE = re.compile(r"^(?!\-)([a-zA-Z0-9\-_]+\.)+[a-zA-Z]{2,}$")


def _parse_clash_line(line: str) -> Rule | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("//"):
        return None
    # YAML payload prefix
    if line.startswith("- "):
        line = line[2:]
    # Loyalsoldier YAML style: '+.domain.com'
    if line.startswith("'+.") and line.endswith("'"):
        return Rule("DOMAIN-SUFFIX", line[3:-1].lower())
    if line.startswith("'") and line.endswith("'"):
        line = line[1:-1]
    # Leading-dot DOMAIN-SUFFIX (our dist format: '.domain.com')
    if line.startswith(".") and _DOMAIN_RE.match(line[1:]):
        return Rule("DOMAIN-SUFFIX", line[1:].lower())
    # Standard Clash: TYPE,value[,policy]
    if "," in line:
        parts = line.split(",", 2)
        rtype = parts[0].upper()
        value = parts[1].lower().strip()
        if rtype in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"):
            return Rule(rtype, value)
        if rtype in ("IP-CIDR", "IP-CIDR6", "IP6-CIDR"):
            return Rule("IP-CIDR6" if ":" in value else "IP-CIDR", value.split(",")[0])
        return None
    # Bare CIDR lines
    if _CIDR4_RE.match(line):
        return Rule("IP-CIDR", line)
    if _CIDR6_RE.match(line):
        return Rule("IP-CIDR6", line)
    # Bare domain line
    if _DOMAIN_RE.match(line):
        return Rule("DOMAIN-SUFFIX", line.lower())
    return None


def parse_clash(text: str) -> list[Rule]:
    rules = []
    in_payload = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "payload:":
            in_payload = True
            continue
        if in_payload and not line.startswith("-"):
            in_payload = False
        rule = _parse_clash_line(line)
        if rule:
            rules.append(rule)
    return rules


def parse_bare(text: str) -> list[Rule]:
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if _CIDR4_RE.match(line):
            rules.append(Rule("IP-CIDR", line))
        elif _CIDR6_RE.match(line):
            rules.append(Rule("IP-CIDR6", line))
        elif _DOMAIN_RE.match(line):
            rules.append(Rule("DOMAIN-SUFFIX", line.lower()))
    return rules


_AUTOPXY_DOMAIN = re.compile(r"^\|\|([a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,})")


def parse_gfwlist(text: str) -> list[Rule]:
    """Decode base64 AutoProxy PAC and extract domains."""
    try:
        decoded = base64.b64decode(text.strip()).decode("utf-8")
    except Exception:
        return []
    rules = []
    for line in decoded.splitlines():
        line = line.strip()
        if not line or line.startswith("!") or line.startswith("[") or line.startswith("@@"):
            continue
        m = _AUTOPXY_DOMAIN.match(line)
        if m:
            rules.append(Rule("DOMAIN-SUFFIX", m.group(1).lower()))
        elif _DOMAIN_RE.match(line):
            rules.append(Rule("DOMAIN-SUFFIX", line.lower()))
    return rules


# ---------------------------------------------------------------------------
# Domain index for fast subsumption checks
# ---------------------------------------------------------------------------

@dataclass
class DomainIndex:
    domains: set[str] = field(default_factory=set)
    suffixes: set[str] = field(default_factory=set)
    cidrs4: list[ipaddress.IPv4Network] = field(default_factory=list)
    cidrs6: list[ipaddress.IPv6Network] = field(default_factory=list)

    def add(self, rule: Rule) -> None:
        if rule.rtype == "DOMAIN":
            self.domains.add(rule.value)
        elif rule.rtype == "DOMAIN-SUFFIX":
            self.suffixes.add(rule.value)
        elif rule.rtype == "IP-CIDR":
            try:
                self.cidrs4.append(ipaddress.ip_network(rule.value, strict=False))
            except ValueError:
                pass
        elif rule.rtype in ("IP-CIDR6", "IP6-CIDR"):
            try:
                self.cidrs6.append(ipaddress.ip_network(rule.value, strict=False))
            except ValueError:
                pass

    def covers(self, rule: Rule) -> bool:
        if rule.rtype in ("DOMAIN", "DOMAIN-SUFFIX"):
            v = rule.value
            # Check exact match in domain set
            if v in self.domains:
                return True
            # Check v or any parent suffix in suffix set
            parts = v.split(".")
            for i in range(len(parts)):
                if ".".join(parts[i:]) in self.suffixes:
                    return True
            return False
        if rule.rtype in ("IP-CIDR", "IP-CIDR6", "IP6-CIDR"):
            try:
                net = ipaddress.ip_network(rule.value, strict=False)
                pool = self.cidrs6 if isinstance(net, ipaddress.IPv6Network) else self.cidrs4
                return any(net.subnet_of(p) for p in pool)
            except ValueError:
                return False
        return False


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

@dataclass
class LoadedCorpus:
    name: str
    rules: list[Rule]
    file_counts: dict[str, int]  # filename → rule count

    @property
    def index(self) -> DomainIndex:
        if not hasattr(self, "_index"):
            idx = DomainIndex()
            for r in self.rules:
                idx.add(r)
            self._index = idx
        return self._index


def load_corpus(defn: CorpusDef) -> LoadedCorpus:
    repo_path = REPO_ROOT / defn.repo
    all_rules: list[Rule] = []
    file_counts: dict[str, int] = {}

    # Resolve file list
    if defn.files == ["__all_mihomo__"]:
        files = git_ls_tree(repo_path, defn.branch, "mihomo/")
        files = [f for f in files if f.endswith(".txt")]
    else:
        files = defn.files

    parser = {"clash": parse_clash, "bare": parse_bare, "gfwlist": parse_gfwlist}[defn.fmt]

    for filepath in files:
        text = git_show(repo_path, defn.branch, filepath)
        if text is None:
            # Try local file for "." repo
            local = repo_path / filepath
            if local.exists():
                text = local.read_text()
        if text is None:
            continue
        rules = parser(text)
        all_rules.extend(rules)
        short = Path(filepath).name
        file_counts[short] = len(rules)

    return LoadedCorpus(name=defn.name, rules=all_rules, file_counts=file_counts)


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------

def coverage(corpus: LoadedCorpus, against: DomainIndex) -> tuple[int, int]:
    """Return (covered, total) rule counts."""
    total = len(corpus.rules)
    covered = sum(1 for r in corpus.rules if against.covers(r))
    return covered, total


def novel_rules(corpus: LoadedCorpus, combined_index: DomainIndex) -> list[Rule]:
    return [r for r in corpus.rules if not combined_index.covers(r)]


# ---------------------------------------------------------------------------
# 666OS wiring check
# ---------------------------------------------------------------------------

def check_666os_wiring(corpus: LoadedCorpus) -> list[str]:
    """Return 666OS filenames not referenced in categories.yaml."""
    cats_path = REPO_ROOT / "source" / "categories.yaml"
    cats_text = cats_path.read_text() if cats_path.exists() else ""
    unwired = []
    for fname in sorted(corpus.file_counts):
        stem = fname.replace(".txt", "")
        if f"666OS/rules" not in cats_text or stem not in cats_text:
            unwired.append(fname)
    return unwired


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def pct(n: int, total: int) -> str:
    if total == 0:
        return "N/A"
    return f"{100 * n / total:.1f}%"


def render_report(corpora: list[LoadedCorpus], novel_cap: int) -> str:
    lines: list[str] = ["# Vendor Coverage Report\n"]

    # --- Corpus summary ---
    lines.append("## Corpus Sizes\n")
    lines.append("| Corpus | Files | Rules |")
    lines.append("|---|---|---|")
    for c in corpora:
        lines.append(f"| {c.name} | {len(c.file_counts)} | {len(c.rules):,} |")
    lines.append("")

    # --- Coverage matrix (domain-type rules only, for clarity) ---
    lines.append("## Coverage Matrix\n")
    lines.append("_% of row corpus's rules subsumed by column corpus_\n")
    names = [c.name for c in corpora]
    header = "| Corpus \\ Covered by |" + "".join(f" {n} |" for n in names)
    sep    = "|---|" + "---|" * len(names)
    lines.append(header)
    lines.append(sep)
    for row in corpora:
        cells = []
        for col in corpora:
            if row.name == col.name:
                cells.append(" — ")
            else:
                cov, tot = coverage(row, col.index)
                cells.append(pct(cov, tot))
        lines.append(f"| {row.name} |" + "".join(f" {c} |" for c in cells))
    lines.append("")

    # --- Combined novel rules ---
    lines.append("## Novel Rules (not subsumed by any other corpus)\n")
    all_others_combined: list[DomainIndex] = []
    for c in corpora:
        idx = DomainIndex()
        for other in corpora:
            if other.name != c.name:
                for r in other.rules:
                    idx.add(r)
        novel = novel_rules(c, idx)
        cap_note = f" (showing first {novel_cap})" if len(novel) > novel_cap else ""
        lines.append(f"### {c.name}: {len(novel):,} novel rules{cap_note}\n")
        for r in novel[:novel_cap]:
            lines.append(f"- `{r.rtype},{r.value}`")
        lines.append("")

    # --- 666OS wiring gaps ---
    os_corpus = next((c for c in corpora if c.name == "666os-release"), None)
    if os_corpus:
        lines.append("## 666OS Files Not Referenced in categories.yaml\n")
        unwired = check_666os_wiring(os_corpus)
        if unwired:
            for f in unwired:
                cnt = os_corpus.file_counts.get(f, 0)
                lines.append(f"- `{f}` ({cnt:,} rules)")
        else:
            lines.append("All 666OS files are referenced.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Vendor corpus coverage validator")
    parser.add_argument("--output", "-o", help="Write report to file (default: stdout)")
    parser.add_argument("--novel-cap", type=int, default=20,
                        help="Max novel rules to show per corpus (default: 20)")
    parser.add_argument("--corpora", nargs="*",
                        help="Limit to specific corpus names (default: all)")
    args = parser.parse_args()

    selected = CORPORA
    if args.corpora:
        selected = [c for c in CORPORA if c.name in args.corpora]

    print(f"Loading {len(selected)} corpora...", file=sys.stderr)
    loaded: list[LoadedCorpus] = []
    for defn in selected:
        sys.stderr.write(f"  {defn.name}... ")
        sys.stderr.flush()
        corpus = load_corpus(defn)
        loaded.append(corpus)
        sys.stderr.write(f"{len(corpus.rules):,} rules\n")

    print("Computing coverage...", file=sys.stderr)
    report = render_report(loaded, args.novel_cap)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
