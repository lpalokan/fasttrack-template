#!/usr/bin/env bash
# The one definition of green. Everything calls this script: the pre-push
# hook with --fast, CI without it, and you or the agent before saying "done".
# The commands live in fasttrack.conf.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
# A hook run from a git worktree exports GIT_DIR; a test's git command would then act on this
# repository instead of its own throwaway one. From here on git finds the repository from the
# working directory, as it does outside a hook. The list includes GIT_CONFIG_PARAMETERS, so
# settings a caller passed with `git -c` do not reach the checks either; they should not.
unset $(git rev-parse --local-env-vars)

conf() {
  python3 tools/guard.py conf "$1"
}

step() {
  echo "check: $1"
  bash -c "$1"
}

lint=$(conf LINT_CMD)
fast=$(conf FAST_TEST_CMD)
full=$(conf FULL_TEST_CMD)

step "python3 -m unittest discover -s tools/tests"
if [ -n "$lint" ]; then step "$lint"; fi

if [ "${1:-}" = "--fast" ]; then
  if [ -n "$fast" ]; then step "$fast"; fi
else
  if [ -n "${full:-$fast}" ]; then step "${full:-$fast}"; fi
fi

if [ -z "$lint$fast$full" ]; then
  echo "check: no project checks configured yet; run scripts/bootstrap.sh" >&2
fi
echo "check: green"
