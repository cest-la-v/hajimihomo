#!/usr/bin/env bash
# push_text.sh — commit changed text rule-set files to ruleset/mihomo and ruleset/singbox branches
#
# Usage: bash scripts/publish/push_text.sh
#
# Expects dist/mihomo/*.yaml and dist/singbox/*.json to exist (written by build.py).
# CI must checkout the target branches alongside the source checkout.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$REPO_ROOT/dist"
DATE="$(date -u +%Y-%m-%d)"

commit_branch() {
    local branch="$1"
    local src_dir="$2"
    local pattern="$3"

    echo "→ Pushing $branch …"

    # work in a temp worktree to avoid disturbing current checkout
    local wt="$REPO_ROOT/.wt-$branch"
    git -C "$REPO_ROOT" worktree add --no-checkout "$wt" "$branch" 2>/dev/null \
        || git -C "$REPO_ROOT" worktree add "$wt" "$branch"

    # copy outputs into worktree
    find "$src_dir" -maxdepth 1 -name "$pattern" -exec cp {} "$wt/" \;

    # also copy rulesets.json catalog if present (only mihomo branch carries it)
    if [[ -f "$DIST/rulesets.json" && "$branch" == "ruleset/mihomo" ]]; then
        cp "$DIST/rulesets.json" "$wt/"
    fi

    # commit only changed files
    git -C "$wt" add -A
    if git -C "$wt" diff --cached --quiet; then
        echo "  no changes on $branch"
    else
        local count
        count=$(git -C "$wt" diff --cached --name-only | wc -l | tr -d ' ')
        git -C "$wt" commit -m "build: update rule-sets · $DATE ($count files changed)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
        git -C "$wt" push origin "$branch"
        echo "  pushed $count file(s) to $branch"
    fi

    git -C "$REPO_ROOT" worktree remove --force "$wt"
}

commit_branch "ruleset/mihomo"  "$DIST/mihomo"  "*.yaml"
commit_branch "ruleset/singbox" "$DIST/singbox" "*.json"

echo "✓ Text rule-sets pushed"
