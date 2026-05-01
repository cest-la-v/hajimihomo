#!/usr/bin/env python3
"""
stats.py — per-build statistics and diff vs previous build.

Fetches build-meta.json from the previous release (releases/latest/download/build-meta.json),
compares with the current dist/build-meta.json, and prints a diff summary.

Usage (called after build.py):
  python3 scripts/stats.py [--dist-dir dist]
"""

import argparse
import json
import logging
import sys
import urllib.request
import urllib.error
from pathlib import Path

PREV_META_URL = (
    "https://github.com/cest-la-v/hajimihomo/releases/latest/download/build-meta.json"
)

log = logging.getLogger("stats")


def fetch_prev_meta() -> dict | None:
    try:
        with urllib.request.urlopen(PREV_META_URL, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.info("No previous release found (first run)")
        else:
            log.warning("Could not fetch previous build-meta: HTTP %s", e.code)
        return None
    except Exception as e:
        log.warning("Could not fetch previous build-meta: %s", e)
        return None


def diff_meta(prev: dict, curr: dict) -> list[str]:
    """Return human-readable diff lines."""
    lines: list[str] = []

    prev_cats = prev.get("categories", {})
    curr_cats = curr.get("categories", {})

    prev_total = prev.get("total_rules", 0)
    curr_total = curr.get("total_rules", 0)
    delta = curr_total - prev_total
    sign = "+" if delta >= 0 else ""
    lines.append(
        f"Total rules: {curr_total:,} ({sign}{delta:,} vs {prev.get('built_at', 'prev')})"
    )
    lines.append("")

    added = sorted(set(curr_cats) - set(prev_cats))
    removed = sorted(set(prev_cats) - set(curr_cats))
    changed: list[tuple[str, int, int]] = []

    for cat, info in curr_cats.items():
        if cat in prev_cats:
            prev_count = prev_cats[cat].get("rule_count", 0)
            curr_count = info.get("rule_count", 0)
            if prev_count != curr_count:
                changed.append((cat, prev_count, curr_count))

    if added:
        lines.append(f"New categories ({len(added)}): {', '.join(added)}")
    if removed:
        lines.append(f"Removed categories ({len(removed)}): {', '.join(removed)}")
    if changed:
        lines.append(f"\nChanged rule counts ({len(changed)}):")
        for cat, prev_n, curr_n in sorted(changed, key=lambda x: abs(x[2] - x[1]), reverse=True)[:20]:
            d = curr_n - prev_n
            sign = "+" if d >= 0 else ""
            lines.append(f"  {cat}: {prev_n:,} → {curr_n:,} ({sign}{d:,})")

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="build stats + diff")
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).parent.parent
    meta_path = repo_root / args.dist_dir / "build-meta.json"

    if not meta_path.exists():
        log.error("build-meta.json not found at %s — run build.py first", meta_path)
        sys.exit(1)

    curr = json.loads(meta_path.read_text())
    prev = fetch_prev_meta()

    print(f"\n=== Build summary: {curr.get('built_at', 'unknown')} ===")
    print(f"Categories built: {curr.get('total_categories', 0)}")
    print(f"Total rules:      {curr.get('total_rules', 0):,}")

    if prev:
        print("\n=== Diff vs previous build ===")
        for line in diff_meta(prev, curr):
            print(line)
    else:
        print("\n(no previous build to diff against)")

    # write stats as GITHUB_STEP_SUMMARY if running in CI
    summary_path = Path(sys.environ.get("GITHUB_STEP_SUMMARY", ""))
    if summary_path.name:
        with summary_path.open("a") as f:
            f.write(f"## Build stats · {curr.get('built_at', '')}\n\n")
            f.write(f"- Categories: {curr.get('total_categories', 0)}\n")
            f.write(f"- Total rules: {curr.get('total_rules', 0):,}\n")
            if prev:
                f.write("\n### Diff vs previous\n\n```\n")
                f.write("\n".join(diff_meta(prev, curr)))
                f.write("\n```\n")


if __name__ == "__main__":
    main()
