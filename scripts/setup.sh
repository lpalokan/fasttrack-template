#!/usr/bin/env bash
# Switch on this repository's git hooks. Safe to run any number of times.
# A SessionStart hook runs it in every Claude Code session, because a fresh
# clone, such as a cloud session's, does not run .githooks until this is set.
set -eu
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* scripts/*.sh tools/guard.py 2>/dev/null || true
echo "setup: git hooks on (.githooks); the rules are in AGENTS.md"
