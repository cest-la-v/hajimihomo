#!/usr/bin/env python3
"""
Binary rule-set smoke-tester.

Checks:
  .srs files  — sing-box compiled rule-set magic bytes (0x00 + "SRS")
  .mrs files  — mihomo binary rule-set magic bytes ("MRS\x00")
  .mmdb files — MaxMind DB magic bytes (\xab\xcd\xefMaxMind.com)

Usage:
  python3 scripts/validate_binaries.py dist/binaries/
"""

import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger("validate_binaries")

# Magic byte signatures
SIGNATURES: dict[str, bytes] = {
    ".srs": b"\x00SRS",          # sing-box compiled rule-set
    ".mrs": b"MRS\x00",          # mihomo binary rule-set
    ".mmdb": b"\xab\xcd\xef",    # MaxMind DB (GeoLite2 / GeoIP2)
}


def check_file(path: Path) -> str | None:
    """Return error string or None if file is valid."""
    suffix = path.suffix.lower()
    expected = SIGNATURES.get(suffix)
    if expected is None:
        return None  # unknown extension, skip

    if path.stat().st_size == 0:
        return f"empty file: {path}"

    with path.open("rb") as f:
        header = f.read(len(expected))

    if header != expected:
        got = header.hex() if header else "(empty)"
        return f"bad magic in {path.name}: expected {expected.hex()}, got {got}"

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="smoke-test binary rule-sets")
    parser.add_argument("dirs", nargs="+", help="directories to check")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    errors = 0
    checked = 0
    for d in args.dirs:
        for path in sorted(Path(d).rglob("*")):
            if not path.is_file():
                continue
            err = check_file(path)
            if err:
                log.error(err)
                errors += 1
            elif path.suffix.lower() in SIGNATURES:
                log.debug("ok: %s", path)
                checked += 1

    if errors:
        log.error("Binary validation FAILED: %d error(s)", errors)
        sys.exit(1)
    else:
        log.info("Binary validation passed (%d files checked)", checked)


if __name__ == "__main__":
    main()
