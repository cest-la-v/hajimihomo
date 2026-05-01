#!/usr/bin/env python3
"""
Extract upstream data sources from blackmatrix7/ios_rule_script Clash README files.
Outputs source/rule/<Category>/sources.yaml for each category.

Usage:
  python3 scripts/extract_sources.py [--vendor-dir vendor/ios_rule_script] [--output-dir source/rule]
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
    parser = argparse.ArgumentParser(description="extract sources.yaml from blackmatrix7 READMEs")
    parser.add_argument("--vendor-dir", default=None,
                        help="path to ios_rule_script checkout (default: vendor/ios_rule_script)")
    parser.add_argument("--output-dir", default=None,
                        help="path to write sources.yaml files (default: source/rule)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    vendor_dir = Path(args.vendor_dir) if args.vendor_dir else repo_root / "vendor/ios_rule_script"
    output_dir = Path(args.output_dir) if args.output_dir else repo_root / "source/rule"
    clash_dir = vendor_dir / "rule" / "Clash"

    if not clash_dir.exists():
        print(f"ERROR: Clash rule dir not found: {clash_dir}", file=sys.stderr)
        sys.exit(1)

    categories = sorted(d.name for d in clash_dir.iterdir() if d.is_dir())
    print(f"Found {len(categories)} categories", file=sys.stderr)

    for cat in categories:
        readme = clash_dir / cat / "README.md"
        if not readme.exists():
            continue
        sources = extract_sources(readme)
        if not sources:
            continue

        out_dir = output_dir / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "sources.yaml"
        with open(out_file, "w") as f:
            f.write(f"# Auto-extracted from blackmatrix7/ios_rule_script rule/Clash/{cat}/README.md\n")
            f.write(f"name: {cat}\n")
            f.write("sources:\n")
            for url in sources:
                f.write(f"  - {url}\n")

    written = len(list(output_dir.glob("*/sources.yaml")))
    print(f"Written {written} sources.yaml files", file=sys.stderr)


if __name__ == "__main__":
    main()

