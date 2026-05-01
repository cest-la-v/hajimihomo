#!/usr/bin/env python3
"""
Extract upstream data sources from blackmatrix7/ios_rule_script Clash README files.
Outputs source/rule/<Category>/sources.yaml for each category.
"""
import os, re, sys
from pathlib import Path

VENDOR = Path("/Users/td/@/v/hajimihomo/vendor/ios_rule_script/rule/Clash")
OUTPUT = Path("/Users/td/@/v/hajimihomo/source/rule")

URL_RE = re.compile(r'https?://\S+')

def extract_sources(readme: Path) -> list[str]:
    text = readme.read_text(encoding="utf-8", errors="ignore")
    # Find the 数据来源 section
    match = re.search(r'## 数据来源(.*?)(?=^##|\Z)', text, re.DOTALL | re.MULTILINE)
    if not match:
        return []
    section = match.group(1)
    urls = URL_RE.findall(section)
    # strip trailing punctuation that might have been captured
    return [u.rstrip("）)。，,") for u in urls]

def main():
    categories = sorted(d.name for d in VENDOR.iterdir() if d.is_dir())
    print(f"Found {len(categories)} categories", file=sys.stderr)

    for cat in categories:
        readme = VENDOR / cat / "README.md"
        if not readme.exists():
            continue
        sources = extract_sources(readme)
        if not sources:
            continue

        out_dir = OUTPUT / cat
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "sources.yaml"
        with open(out_file, "w") as f:
            f.write(f"# Auto-extracted from blackmatrix7/ios_rule_script rule/Clash/{cat}/README.md\n")
            f.write(f"name: {cat}\n")
            f.write(f"sources:\n")
            for url in sources:
                f.write(f"  - {url}\n")

    written = len(list(OUTPUT.glob("*/sources.yaml")))
    print(f"Written {written} sources.yaml files", file=sys.stderr)

if __name__ == "__main__":
    main()
