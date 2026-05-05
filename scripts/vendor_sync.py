#!/usr/bin/env python3
"""
vendor_sync.py — Clone or update all repos referenced by repo: sources in categories.yaml.

For each unique owner/repo found, either:
  - shallow-clone with --filter=blob:none (blobless) if not yet present, or
  - git fetch the required refs if already cloned.

Usage:
    python3 scripts/vendor_sync.py [--dry-run] [--jobs N]
"""

import argparse
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
VENDOR = REPO_ROOT / "vendor"
CATS = REPO_ROOT / "source" / "categories.yaml"


def parse_repo_sources(cats_path: Path) -> dict[str, set[str]]:
    """Return {owner/repo: {ref, ...}} for all repo: sources in categories.yaml."""
    data = yaml.safe_load(cats_path.read_text())
    repo_refs: dict[str, set[str]] = defaultdict(set)
    for cat in data.values():
        for src in cat.get("sources", []):
            if not src.startswith("repo:"):
                continue
            parts = src[5:].split("/", 3)
            if len(parts) < 3:
                continue
            owner_repo = f"{parts[0]}/{parts[1]}"
            ref = parts[2]
            repo_refs[owner_repo].add(ref)
    return repo_refs


def sync_repo(owner_repo: str, refs: set[str], dry_run: bool) -> str:
    vendor_dir = VENDOR / owner_repo
    gh_url = f"https://github.com/{owner_repo}.git"

    if not vendor_dir.exists():
        action = f"clone {gh_url}"
        if dry_run:
            return f"[dry-run] would {action}"
        vendor_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", "--depth=1",
             gh_url, str(vendor_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return f"ERROR cloning {owner_repo}: {result.stderr.strip()}"
        action_done = "cloned"
    else:
        action_done = "fetched"

    # Fetch each required ref at depth=1 to make it available for git-show.
    # Skip if ref already resolves locally (e.g. it's the default branch fetched by clone).
    fetch_errors = []
    for ref in sorted(refs):
        if dry_run:
            continue
        already = subprocess.run(
            ["git", "-C", str(vendor_dir), "rev-parse", "--verify", f"origin/{ref}"],
            capture_output=True,
        )
        if already.returncode == 0:
            continue  # already available
        result = subprocess.run(
            ["git", "-C", str(vendor_dir), "fetch", "--depth=1", "origin", ref],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Only warn if origin/HEAD isn't available either — if it is,
            # parse.py will fall back to origin/HEAD and the repo is usable.
            head_ok = subprocess.run(
                ["git", "-C", str(vendor_dir), "rev-parse", "--verify", "origin/HEAD"],
                capture_output=True,
            )
            if head_ok.returncode != 0:
                fetch_errors.append(f"{ref}: {result.stderr.strip()[:80]}")

    refs_str = ", ".join(sorted(refs))
    if fetch_errors:
        return f"{action_done} {owner_repo} ({refs_str}) — fetch warnings: {'; '.join(fetch_errors)}"
    return f"{action_done} {owner_repo} ({refs_str})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync vendor repos for repo: sources")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel clone/fetch jobs")
    args = parser.parse_args()

    repo_refs = parse_repo_sources(CATS)
    total = len(repo_refs)
    already = sum(1 for r in repo_refs if (VENDOR / r).exists())
    new = total - already

    print(f"Found {total} unique repos ({already} already cloned, {new} to clone)")
    if args.dry_run:
        print("[dry-run mode — no changes will be made]")

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(sync_repo, owner_repo, refs, args.dry_run): owner_repo
            for owner_repo, refs in repo_refs.items()
        }
        for future in as_completed(futures):
            owner_repo = futures[future]
            try:
                msg = future.result()
                print(f"  {msg}")
            except Exception as exc:
                print(f"  ERROR {owner_repo}: {exc}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    main()
