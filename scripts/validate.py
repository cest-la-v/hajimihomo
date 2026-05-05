#!/usr/bin/env python3
"""
Source rule linter.

Validates source/categories.yaml:
  - YAML parses cleanly
  - Each category has a 'sources' list of https:// URLs
  - Each URL points to a known raw file host

Optionally fetches each URL and reports parse errors (--fetch).

Usage:
  python3 scripts/validate.py [--fetch] [--categories-file source/categories.yaml]
"""

import argparse
import logging
import sys
import urllib.request
import urllib.error
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from convert.parse import fetch_and_parse

ALLOWED_HOSTS = {
    "raw.githubusercontent.com",
    "gist.githubusercontent.com",
    "cdn.jsdelivr.net",
    "fastly.jsdelivr.net",
    "raw.githubusercontents.com",
    "gitlab.com",
    "bitbucket.org",
}

log = logging.getLogger("validate")


def validate_category(name: str, entry: dict) -> list[str]:
    """Return list of error strings; empty = valid."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{name}: entry must be a mapping"]

    sources = entry.get("sources", [])
    if sources and not isinstance(sources, list):
        errors.append(f"{name}: 'sources' must be a list")
        return errors

    for i, url in enumerate(sources or []):
        if not isinstance(url, str):
            errors.append(f"{name}: source[{i}] is not a string: {url!r}")
            continue
        if not url.startswith("https://"):
            errors.append(f"{name}: source[{i}] not https: {url}")
        host = url.split("/")[2] if "/" in url[8:] else url[8:]
        if host not in ALLOWED_HOSTS:
            log.warning("  unknown host in %s: %s", name, host)

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="validate source rules")
    parser.add_argument("--fetch", action="store_true", help="also fetch and parse each URL")
    parser.add_argument("--categories-file", default="source/categories.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).parent.parent
    categories_file = repo_root / args.categories_file

    data = yaml.safe_load(categories_file.read_text()) or {}
    log.info("Validating %d categories in %s", len(data), categories_file)

    total_errors = 0
    for name, entry in data.items():
        errors = validate_category(name, entry)
        if errors:
            for e in errors:
                log.error("  %s", e)
            total_errors += len(errors)
        else:
            log.debug("  %s: ok", name)

    if args.fetch:
        log.info("Fetching and parsing all source URLs…")
        for name, entry in data.items():
            for url in (entry or {}).get("sources", []):
                try:
                    rules = fetch_and_parse(url)
                    log.debug("  %s: %d rules", url, len(rules))
                except RuntimeError as e:
                    log.error("  FETCH ERROR: %s", e)
                    total_errors += 1

    if total_errors:
        log.error("Validation FAILED: %d error(s)", total_errors)
        sys.exit(1)
    else:
        log.info("Validation passed")


if __name__ == "__main__":
    main()
