#!/usr/bin/env python3
"""
Extract upstream data sources from blackmatrix7/ios_rule_script Clash README files.
Outputs source/categories.yaml with all categories merged into one file.

Usage:
  python3 scripts/extract_sources.py [--vendor-dir vendor/ios_rule_script] [--output source/categories.yaml]
"""
import argparse
import re
import sys
from pathlib import Path

URL_RE = re.compile(r'https?://\S+')


def extract_sources(readme: Path) -> list[str]:
    text = readme.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'## 数据来源(.*?)(?=^##|\Z)', text, re.DOTALL | re.MULTILINE)
    if not match:
        return []
    section = match.group(1)
    urls = URL_RE.findall(section)
    return [u.rstrip("）)。，,") for u in urls]


def main() -> None:
    parser = argparse.ArgumentParser(description="extract sources from blackmatrix7 READMEs into categories.yaml")
    parser.add_argument("--vendor-dir", default=None,
                        help="path to ios_rule_script checkout (default: vendor/blackmatrix7/ios_rule_script)")
    parser.add_argument("--output", default=None,
                        help="output file (default: source/categories.yaml)")
    parser.add_argument("--check", action="store_true",
                        help="report coverage gaps without writing output")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    vendor_dir = Path(args.vendor_dir) if args.vendor_dir else repo_root / "vendor/blackmatrix7/ios_rule_script"
    out_file = Path(args.output) if args.output else repo_root / "source/categories.yaml"
    clash_dir = vendor_dir / "rule" / "Clash"

    if not clash_dir.exists():
        print(f"ERROR: Clash rule dir not found: {clash_dir}", file=sys.stderr)
        sys.exit(1)

    # Load existing categories.yaml to preserve append/exclude entries
    # Keys are normalised to str (YAML parses bare numbers as int)
    existing: dict[str, dict] = {}
    if out_file.exists():
        import yaml
        raw = yaml.safe_load(out_file.read_text()) or {}
        existing = {str(k): v for k, v in raw.items()}

    BM7_RAW = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master"

    def has_clash_content(cat: str) -> bool:
        """Return True if bm7's built Clash list for this category has actual rules."""
        f = clash_dir / cat / f"{cat}.list"
        if not f.exists():
            return False
        return any(l.strip() and not l.startswith("#") for l in f.read_text().splitlines())

    def fallback_source(cat: str) -> list[str]:
        """For categories with no upstream data sources, use the built Clash URL directly."""
        if has_clash_content(cat):
            return [f"{BM7_RAW}/rule/Clash/{cat}/{cat}.list"]
        return []

    categories = sorted(d.name for d in clash_dir.iterdir() if d.is_dir())
    print(f"Found {len(categories)} categories in bm7", file=sys.stderr)

    if args.check:
        our = set(existing.keys())
        bm7_cats = set()
        for cat in categories:
            readme = clash_dir / cat / "README.md"
            if not readme.exists():
                continue
            if extract_sources(readme) or has_clash_content(cat):
                bm7_cats.add(cat)
        missing = sorted(bm7_cats - our)
        extra = sorted(our - bm7_cats)
        print(f"Our categories.yaml: {len(our)}")
        print(f"bm7 categories with content: {len(bm7_cats)}")
        if missing:
            print(f"\nIn bm7 but MISSING from categories.yaml ({len(missing)}):")
            for c in missing:
                print(f"  {c}")
        else:
            print("\nNo missing categories — full coverage!")
        if extra:
            print(f"\nIn categories.yaml but not in bm7 ({len(extra)}):")
            for c in extra:
                print(f"  {c}")
        return

    # Quote category names that are pure numbers to avoid YAML parsing them as int
    def yaml_key(name: str) -> str:
        return f'"{name}"' if name.isdigit() else name

    lines = [
        "# Auto-extracted from blackmatrix7/ios_rule_script — do not edit manually.",
        "# To add custom rules, create source/overrides/<Category>.append.list",
        "# or source/overrides/<Category>.remove.list and reference them here.",
        "",
    ]
    written = 0
    for cat in categories:
        readme = clash_dir / cat / "README.md"
        if not readme.exists():
            continue
        sources = extract_sources(readme)
        # Fallback: categories with no upstream sources use bm7's own built Clash list
        if not sources:
            sources = fallback_source(cat)
        prev = existing.get(cat) or {}
        overrides = {k: prev[k] for k in ("append", "exclude") if k in prev}
        if not sources and not overrides:
            continue  # skip empty entries
        lines.append(f"{yaml_key(cat)}:")
        if sources:
            lines.append("  sources:")
            for url in sources:
                lines.append(f"    - {url}")
            written += 1
        for key, refs in overrides.items():
            lines.append(f"  {key}:")
            for ref in refs:
                lines.append(f"    - {ref}")
        lines.append("")

    # Preserve custom categories that exist in our config but not in bm7
    bm7_cats = set(categories)
    for cat, entry in existing.items():
        if cat not in bm7_cats and isinstance(entry, dict):
            lines.append(f"{yaml_key(cat)}:")
            for key in ("sources", "append", "exclude"):
                if key in entry:
                    lines.append(f"  {key}:")
                    for ref in entry[key]:
                        lines.append(f"    - {ref}")
            lines.append("")

    out_file.write_text("\n".join(lines))
    print(f"Written {written} categories (+custom) to {out_file} ({out_file.stat().st_size // 1024}KB)", file=sys.stderr)


if __name__ == "__main__":
    main()

