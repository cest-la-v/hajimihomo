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
                        help="path to ios_rule_script checkout (default: vendor/ios_rule_script)")
    parser.add_argument("--output", default=None,
                        help="output file (default: source/categories.yaml)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    vendor_dir = Path(args.vendor_dir) if args.vendor_dir else repo_root / "vendor/ios_rule_script"
    out_file = Path(args.output) if args.output else repo_root / "source/categories.yaml"
    clash_dir = vendor_dir / "rule" / "Clash"

    if not clash_dir.exists():
        print(f"ERROR: Clash rule dir not found: {clash_dir}", file=sys.stderr)
        sys.exit(1)

    # Load existing categories.yaml to preserve append/exclude entries
    existing: dict[str, dict] = {}
    if out_file.exists():
        import yaml
        existing = yaml.safe_load(out_file.read_text()) or {}

    categories = sorted(d.name for d in clash_dir.iterdir() if d.is_dir())
    print(f"Found {len(categories)} categories", file=sys.stderr)

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
        prev = existing.get(cat, {})
        lines.append(f"{cat}:")
        if sources:
            lines.append("  sources:")
            for url in sources:
                lines.append(f"    - {url}")
            written += 1
        # Preserve hand-maintained append/exclude entries
        for key in ("append", "exclude"):
            if key in prev:
                lines.append(f"  {key}:")
                for ref in prev[key]:
                    lines.append(f"    - {ref}")
        lines.append("")

    out_file.write_text("\n".join(lines))
    print(f"Written {written} categories to {out_file} ({out_file.stat().st_size // 1024}KB)", file=sys.stderr)


if __name__ == "__main__":
    main()

