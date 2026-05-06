#!/usr/bin/env python3
"""
vendor_sync.py — Clone or update all repos referenced by repo: sources in categories.yaml.

For each unique owner/repo found, either:
  - shallow-clone (--depth=1 --single-branch) if not yet present, or
  - git fetch --depth=1 the required ref if already cloned.

Working tree is always checked out, so files can be read directly from the filesystem
without git-show. Blobs are present for the current commit only (no history).

Usage:
    python3 scripts/vendor_sync.py [--dry-run] [--jobs N] [--reclone]
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


def _is_blobless(vendor_dir: Path) -> bool:
    """Return True if the repo was cloned with --filter=blob:none."""
    result = subprocess.run(
        ["git", "-C", str(vendor_dir), "config", "remote.origin.partialclonefilter"],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and "blob:none" in result.stdout


def sync_repo(owner_repo: str, refs: set[str], dry_run: bool, reclone: bool) -> str:
    vendor_dir = VENDOR / owner_repo
    gh_url = f"https://github.com/{owner_repo}.git"

    # All repos use exactly one ref in practice — use it as the clone branch.
    primary_ref = sorted(refs)[0]

    if vendor_dir.exists() and _is_blobless(vendor_dir):
        if dry_run:
            return f"[dry-run] would reclone {owner_repo} (blobless → shallow)"
        # Reclone: blobless clones can't be read from the filesystem without
        # network access. Remove and re-clone with --depth=1.
        import shutil
        shutil.rmtree(vendor_dir)
        action = "recloned"
    elif vendor_dir.exists() and not reclone:
        action = "updated"
    elif vendor_dir.exists():
        if dry_run:
            return f"[dry-run] would reclone {owner_repo}"
        import shutil
        shutil.rmtree(vendor_dir)
        action = "recloned"
    else:
        action = "cloned"

    if not vendor_dir.exists():
        if dry_run:
            return f"[dry-run] would clone {gh_url} @ {primary_ref}"
        vendor_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", "--single-branch",
             "--branch", primary_ref, gh_url, str(vendor_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Branch may not exist by that name — fall back to default branch
            result = subprocess.run(
                ["git", "clone", "--depth=1", "--single-branch",
                 gh_url, str(vendor_dir)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                return f"ERROR cloning {owner_repo}: {result.stderr.strip()}"
        return f"{action} {owner_repo} ({primary_ref})"

    # Already exists and not recloning — fetch latest and checkout correct branch.
    if dry_run:
        return f"[dry-run] would fetch {owner_repo} ({primary_ref})"
    result = subprocess.run(
        ["git", "-C", str(vendor_dir), "fetch", "--depth=1", "origin",
         f"{primary_ref}:refs/remotes/origin/{primary_ref}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        # Switch (or reset) working tree to the target branch
        subprocess.run(
            ["git", "-C", str(vendor_dir), "checkout", "-f", "-B",
             primary_ref, f"origin/{primary_ref}"],
            capture_output=True,
        )
    else:
        # Try via origin/HEAD (handles main/master mismatch)
        head_ok = subprocess.run(
            ["git", "-C", str(vendor_dir), "rev-parse", "--verify", "origin/HEAD"],
            capture_output=True,
        )
        if head_ok.returncode != 0:
            return f"fetch warning {owner_repo} ({primary_ref}): {result.stderr.strip()[:80]}"

    return f"{action} {owner_repo} ({primary_ref})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync vendor repos for repo: sources")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel clone/fetch jobs")
    parser.add_argument("--reclone", action="store_true", help="Force reclone all repos")
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
            pool.submit(sync_repo, owner_repo, refs, args.dry_run, args.reclone): owner_repo
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
