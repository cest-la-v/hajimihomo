#!/usr/bin/env bash
# push_binaries.sh — validate, package, and publish binary rule-sets as a dated GitHub Release
#
# Workflow:
#   1. Validate binary files (magic bytes)
#   2. Generate SHA-256 checksums
#   3. Create dated release (assets not yet "latest" — old release still serving)
#   4. Flip "latest" pointer atomically
#   5. Delete previous release (keep last 3; first-run safe)
#
# Usage: bash scripts/publish/push_binaries.sh [--binaries-dir dist/binaries]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BINARIES_DIR="${1:-$REPO_ROOT/dist/binaries}"
DATE="$(date -u +%Y%m%d)"
TAG="binaries-$DATE"

echo "→ Validating binaries in $BINARIES_DIR …"
python3 "$REPO_ROOT/scripts/validate_binaries.py" "$BINARIES_DIR"

echo "→ Generating SHA-256 checksums …"
pushd "$BINARIES_DIR" > /dev/null
for f in *; do
    [[ -f "$f" && "$f" != *.sha256sum ]] && sha256sum "$f" > "$f.sha256sum"
done
popd > /dev/null

# build-meta.json must also be in the release
cp "$REPO_ROOT/dist/build-meta.json" "$BINARIES_DIR/build-meta.json"

echo "→ Creating release $TAG …"
gh release create "$TAG" \
    --title "binaries · $(date -u +%Y-%m-%d)" \
    --notes "Automated build $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$BINARIES_DIR"/*

echo "→ Flipping latest pointer …"
gh release edit "$TAG" --latest

# keep last 3 releases; delete older ones (first-run safe: PREV_TAG empty = no-op)
PREV_TAGS=$(gh release list --limit 10 --json tagName \
    | python3 -c "
import json, sys
tags = [r['tagName'] for r in json.load(sys.stdin) if r['tagName'].startswith('binaries-')]
# skip the one we just created (it's already listed)
older = [t for t in tags if t != '$TAG']
# delete beyond the 2 most recent previous (keep current + 2 prev = 3 total)
for t in older[2:]:
    print(t)
")

for old_tag in $PREV_TAGS; do
    echo "→ Deleting old release $old_tag …"
    gh release delete "$old_tag" --yes --cleanup-tag || true
done

echo "✓ Binaries released as $TAG (latest)"
