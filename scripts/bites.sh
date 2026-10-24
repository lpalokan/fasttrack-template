#!/usr/bin/env bash
# Bites: every test file this branch adds must fail on the code before the
# change. A test that passes there would pass on code that does nothing.
# The one way past is a "Characterises: <test file>" line in a commit message.
#
# Runs in the pre-push hook and in CI. Usage: scripts/bites.sh [--base REF]
set -euo pipefail
root=$(git rev-parse --show-toplevel)
exec python3 "$root/tools/guard.py" bites "$@"
