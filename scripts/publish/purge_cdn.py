#!/usr/bin/env python3
"""
purge_cdn.py — parallel jsDelivr CDN cache purge for text rule-set branches.

jsDelivr has two CDN hostnames; both need purging after a branch push:
  https://cdn.jsdelivr.net/gh/<repo>@<branch>/<file>
  https://fastly.jsdelivr.net/gh/<repo>@<branch>/<file>

NOTE: jsDelivr @branch URLs are for TEXT files only (yaml/json committed to branches).
      Binary release assets use GitHub's own CDN — no purge needed.

Usage:
  python3 scripts/publish/purge_cdn.py --branch ruleset/mihomo [--branch ruleset/singbox]
  python3 scripts/publish/purge_cdn.py --files dist/mihomo/*.yaml  (purges all changed files)
"""

import argparse
import concurrent.futures
import logging
import sys
import time
import urllib.request
from pathlib import Path

REPO = "cest-la-v/hajimihomo"
CDN_HOSTS = [
    "cdn.jsdelivr.net",
    "fastly.jsdelivr.net",
]
PURGE_BASE = "https://purge.jsdelivr.net/gh/{repo}@{branch}/{file}"

log = logging.getLogger("purge_cdn")


def purge_url(url: str) -> tuple[str, int]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return url, resp.status
    except Exception as e:
        return url, -1


def build_purge_urls(branch: str, filenames: list[str]) -> list[str]:
    urls = []
    for host in CDN_HOSTS:
        base = f"https://purge.jsdelivr.net/gh/{REPO}@{branch}"
        for name in filenames:
            urls.append(f"{base}/{name}")
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description="purge jsDelivr CDN cache")
    parser.add_argument("--branch", action="append", dest="branches",
                        default=[], help="branch name (repeatable)")
    parser.add_argument("--dist-dir", default="dist", help="dist directory")
    parser.add_argument("--jobs", type=int, default=20)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).parent.parent.parent
    dist = repo_root / args.dist_dir

    branches = args.branches or ["ruleset/mihomo", "ruleset/singbox"]

    all_urls: list[str] = []
    for branch in branches:
        suffix = "yaml" if "mihomo" in branch else "json"
        src = dist / branch.split("/")[-1]
        if src.exists():
            filenames = [p.name for p in src.glob(f"*.{suffix}")]
        else:
            log.warning("dist dir not found for %s, skipping", branch)
            continue
        all_urls.extend(build_purge_urls(branch, filenames))

    if not all_urls:
        log.warning("no URLs to purge")
        return

    log.info("Purging %d URLs across %d CDN hosts …", len(all_urls), len(CDN_HOSTS))
    errors = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for url, status in pool.map(purge_url, all_urls):
            if status == 200:
                log.debug("  purged: %s", url)
            else:
                log.warning("  purge failed (%s): %s", status, url)
                errors += 1

    if errors:
        log.warning("CDN purge completed with %d error(s) (non-fatal)", errors)
    else:
        log.info("CDN purge complete")


if __name__ == "__main__":
    main()
