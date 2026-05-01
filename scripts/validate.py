#!/usr/bin/env python3
"""
Source rule linter.

Validates source/rule/*/sources.yaml:
  - YAML parses cleanly
  - 'sources' key is a non-empty list of strings
  - Each URL is https:// pointing to a raw file host

Optionally fetches each URL and reports parse errors (--fetch).

Usage:
  python3 scripts/validate.py [--fetch] [--source-dir source/rule]
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


def validate_sources_yaml(path: Path) -> list[str]:
    """Return list of error strings; empty = valid."""
    errors: list[str] = []
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["root must be a mapping"]

    sources = data.get("sources")
    if not sources:
        errors.append("missing or empty 'sources' key")
        return errors

    if not isinstance(sources, list):
        errors.append("'sources' must be a list")
        return errors

    for i, url in enumerate(sources):
        if not isinstance(url, str):
            errors.append(f"source[{i}] is not a string: {url!r}")
            continue
        if not url.startswith("https://"):
            errors.append(f"source[{i}] not https: {url}")
        host = url.split("/")[2] if "/" in url[8:] else url[8:]
        if host not in ALLOWED_HOSTS:
            log.warning("  unknown host in %s: %s", path.parent.name, host)

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="validate source rules")
    parser.add_argument("--fetch", action="store_true", help="also fetch and parse each URL")
    parser.add_argument("--source-dir", default="source/rule")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).parent.parent
    source_dir = repo_root / args.source_dir

    files = sorted(source_dir.glob("*/sources.yaml"))
    log.info("Validating %d sources.yaml files", len(files))

    total_errors = 0
    for f in files:
        errors = validate_sources_yaml(f)
        if errors:
            for e in errors:
                log.error("  %s: %s", f.parent.name, e)
            total_errors += len(errors)
        else:
            log.debug("  %s: ok", f.parent.name)

    if args.fetch:
        log.info("Fetching and parsing all source URLs…")
        for f in files:
            data = yaml.safe_load(f.read_text())
            for url in data.get("sources", []):
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
