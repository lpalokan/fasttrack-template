#!/usr/bin/env bash
# Set this baseline up for one project: fill fasttrack.conf for the stack,
# describe the project in AGENTS.md, move the template README aside, record
# the decision and switch on the git hooks.
#
# In a fresh fork, with questions:      scripts/bootstrap.sh
# In a fresh fork, without questions:   scripts/bootstrap.sh --name app --description "..." --owner me --stack python --yes
# Into an existing repository:          scripts/bootstrap.sh --into ../my-app
#
# In Claude Code, /bootstrap runs the same script after asking you about the
# project, then fills in the parts a script cannot guess.
set -euo pipefail

template=$(cd "$(dirname "$0")/.." && pwd)

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap.sh [options]

  --name NAME             project name
  --description TEXT      one or two sentences: what the project is
  --owner HANDLE          GitHub handle of the person who merges
  --stack STACK           python, node, go, rust or other
  --lint CMD              override the preset lint command
  --fast CMD              override the fast test command (before every push)
  --full CMD              override the full test command (in CI)
  --test-cmd CMD          command that runs one test file ({file}, {dir}, {stem})
  --test-patterns GLOBS   space-separated globs that pick out test files
  --share PATHS           paths the old checkout borrows during bites
  --into DIR              copy the baseline into an existing repository first
  --yes                   take defaults instead of asking
EOF
}

name="" description="" owner="" stack="" into="" yes=""
lint="" fast="" full="" test_cmd="" test_patterns="" share=""
given=" "

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --yes|-y) yes=1; shift; continue ;;
  esac
  if [ $# -lt 2 ]; then
    echo "bootstrap: $1 needs a value" >&2
    exit 2
  fi
  case "$1" in
    --into) into=$2 ;;
    --name) name=$2 ;;
    --description) description=$2 ;;
    --owner) owner=$2 ;;
    --stack) stack=$2 ;;
    --lint) lint=$2; given+="lint " ;;
    --fast) fast=$2; given+="fast " ;;
    --full) full=$2; given+="full " ;;
    --test-cmd) test_cmd=$2; given+="test_cmd " ;;
    --test-patterns) test_patterns=$2; given+="test_patterns " ;;
    --share) share=$2; given+="share " ;;
    *) echo "bootstrap: unknown option $1" >&2; usage >&2; exit 2 ;;
  esac
  shift 2
done

# The files the hooks and CI run. Bootstrap never leaves one of yours in
# their place, because the hooks would then run your file with our meaning.
mechanisms="fasttrack.conf tools/guard.py scripts/bootstrap.sh scripts/setup.sh
scripts/check.sh scripts/bites.sh .githooks/commit-msg .githooks/pre-push"

# --- into an existing repository: copy, never overwrite, then work there ---
if [ -n "$into" ]; then
  target=$(cd "$into" && pwd)
  if ! git -C "$target" rev-parse --git-dir >/dev/null 2>&1; then
    echo "bootstrap: $into is not a git repository" >&2
    exit 2
  fi
  clashes=""
  for file in $mechanisms; do
    if [ -e "$target/$file" ]; then clashes="$clashes $file"; fi
  done
  if [ -n "$clashes" ]; then
    echo "bootstrap: these files already exist in $into, and the baseline's hooks and CI run them:" >&2
    for file in $clashes; do echo "  $file" >&2; done
    echo "Rename or remove yours, then run bootstrap again. Nothing was copied." >&2
    exit 2
  fi
  kept=""
  while IFS= read -r file; do
    case "$file" in
      README.md|LICENSE) continue ;;
    esac
    if [ -e "$target/$file" ]; then
      kept="$kept $file"
      continue
    fi
    mkdir -p "$target/$(dirname "$file")"
    cp -p "$template/$file" "$target/$file"
  done < <(git -C "$template" ls-files)
  mkdir -p "$target/docs"
  if [ ! -e "$target/docs/fasttrack.md" ]; then
    cp "$template/README.md" "$target/docs/fasttrack.md"
  fi
  if [ -n "$kept" ]; then
    echo "bootstrap: kept your existing files; merge the baseline's versions by hand:"
    for file in $kept; do echo "  $file"; done
  fi
  workdir=$target
else
  workdir=$template
fi

cd "$workdir"

if [ "$(python3 tools/guard.py conf BOOTSTRAPPED)" = "yes" ]; then
  echo "bootstrap: this project is already bootstrapped (fasttrack.conf). Edit fasttrack.conf and AGENTS.md directly, or set BOOTSTRAPPED=\"no\" to start over." >&2
  exit 2
fi

has() {
  case "$given" in *" $1 "*) return 0 ;; esac
  return 1
}

ask() {
  local var=$1 prompt=$2 default=${3:-} reply
  if [ -n "${!var}" ]; then return 0; fi
  if [ -n "$yes" ] || [ ! -t 0 ]; then
    printf -v "$var" '%s' "$default"
    return 0
  fi
  read -r -p "$prompt${default:+ [$default]}: " reply
  printf -v "$var" '%s' "${reply:-$default}"
}

detect_stack() {
  if [ -e pyproject.toml ] || [ -e requirements.txt ] || [ -e setup.py ]; then echo python
  elif [ -e package.json ]; then echo node
  elif [ -e go.mod ]; then echo go
  elif [ -e Cargo.toml ]; then echo rust
  else echo other
  fi
}

detect_owner() {
  local url
  url=$(git remote get-url origin 2>/dev/null || true)
  if [[ $url =~ github\.com[:/]([^/]+)/ ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    echo "${USER:-owner}"
  fi
}

detect_default_branch() {
  local ref
  ref=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
  if [ -n "$ref" ]; then
    echo "${ref#origin/}"
    return 0
  fi
  ref=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)
  echo "${ref:-main}"
}

default_branch=$(detect_default_branch)
protected=$default_branch
for branch in main master; do
  if [ "$branch" != "$default_branch" ]; then protected="$protected $branch"; fi
done

ask name "Project name" "$(basename "$PWD")"
ask description "What is it, in one or two sentences" ""
ask owner "GitHub handle of the person who merges" "$(detect_owner)"
ask stack "Stack (python, node, go, rust, other)" "$(detect_stack)"

p_lint="" p_fast="" p_full="" p_test="" p_patterns="" p_share=""
case "$stack" in
  python)
    p_lint="ruff check ."
    p_fast="python3 -m pytest -q -x"
    p_full="python3 -m pytest -q"
    p_test="python3 -m pytest -q {file}"
    p_patterns="tests/*test_*.py tests/*_test.py"
    ;;
  node)
    p_lint="npm run lint --if-present"
    p_fast="npm test --if-present"
    p_full="npm test --if-present"
    p_test="npm test -- {file}"
    p_patterns="*.test.* *.spec.*"
    p_share="node_modules"
    ;;
  go)
    p_lint="go vet ./..."
    p_fast="go test -short ./..."
    p_full="go test ./..."
    p_test="go test ./{dir}"
    p_patterns="*_test.go"
    ;;
  rust)
    p_lint="cargo clippy --all-targets -- -D warnings"
    p_fast="cargo test --lib"
    p_full="cargo test"
    p_test="cargo test --test {stem}"
    p_patterns="tests/*.rs"
    ;;
  other|none)
    stack=other
    ;;
  *)
    echo "bootstrap: unknown stack '$stack'; use python, node, go, rust or other" >&2
    exit 2
    ;;
esac

has lint || lint=$p_lint
has fast || fast=$p_fast
has full || full=$p_full
has test_cmd || test_cmd=$p_test
has test_patterns || test_patterns=$p_patterns
has share || share=$p_share

if [ "$stack" = other ]; then
  ask lint "Lint command (empty for none)" ""
  ask fast "Fast test command, run before every push" ""
  ask full "Full test command, run in CI" ""
  ask test_cmd "Command that runs one test file, with {file}" ""
  ask test_patterns "Globs that pick out test files" ""
fi

today=$(date +%Y-%m-%d)

cat > fasttrack.conf <<EOF
# fasttrack.conf: this project's commands, in one place.
# Read by scripts/check.sh, tools/guard.py and CI. KEY="value" lines only,
# with no shell expansion. Written by scripts/bootstrap.sh on $today.

PROJECT_NAME="$name"
OWNER="$owner"
STACK="$stack"
BOOTSTRAPPED="yes"
DEFAULT_BRANCH="$default_branch"
PROTECTED_BRANCHES="$protected"

# The one definition of green (scripts/check.sh).
# LINT_CMD runs everywhere. FAST_TEST_CMD runs before every push, so keep it
# under a minute. FULL_TEST_CMD runs in CI, before merge; empty means FAST.
LINT_CMD="$lint"
FAST_TEST_CMD="$fast"
FULL_TEST_CMD="$full"

# Bites: each test file a branch adds must fail on the code before the change.
# TEST_CMD runs one test file. Placeholders: {file} the path, {dir} its folder,
# {stem} its name without the extension. TEST_PATTERNS picks out test files.
# BITES_SHARE lists paths to share with the old checkout, such as node_modules.
TEST_CMD="$test_cmd"
TEST_PATTERNS="$test_patterns"
BITES_SHARE="$share"
BITES_TIMEOUT="600"
EOF

# Describe the project where every session reads it, record the decision,
# and move the template's README aside. Each step looks for its marker, so a
# file you already had is left alone.
python3 - "$name" "$description" "$stack" "$today" "$default_branch" <<'PY'
import re
import sys
from pathlib import Path

name, description, stack, today, default_branch = sys.argv[1:]

agents = Path("AGENTS.md")
if agents.exists():
    text = agents.read_text(encoding="utf-8")
    block = f"<!-- fasttrack:project -->\n**{name}**: {description}\n<!-- /fasttrack:project -->"
    new = re.sub(
        r"<!-- fasttrack:project -->.*?<!-- /fasttrack:project -->",
        lambda _match: block,
        text,
        flags=re.S,
    )
    if new != text:
        agents.write_text(new, encoding="utf-8")
    else:
        print("bootstrap: AGENTS.md has no fasttrack:project block; describe the project there yourself")

decisions = Path("docs/decisions.md")
marker = "<!-- fasttrack:dec-1-amendments -->"
if decisions.exists():
    text = decisions.read_text(encoding="utf-8")
    if marker in text:
        line = f"- Amended {today}: bootstrapped for {name} (stack: {stack}) by scripts/bootstrap.sh."
        decisions.write_text(text.replace(marker, marker + "\n" + line), encoding="utf-8")

ci = Path(".github/workflows/ci.yml")
if ci.exists():
    text = ci.read_text(encoding="utf-8")
    ci.write_text(text.replace("branches: [main]", f"branches: [{default_branch}]"), encoding="utf-8")

readme = Path("README.md")
if readme.exists() and "<!-- fasttrack:template-readme -->" in readme.read_text(encoding="utf-8"):
    Path("docs").mkdir(exist_ok=True)
    Path("docs/fasttrack.md").write_text(readme.read_text(encoding="utf-8"), encoding="utf-8")
    readme.write_text(
        f"# {name}\n\n{description}\n\n"
        "## Working on it\n\n"
        "The conventions are in AGENTS.md, the decisions and their reasons in "
        "docs/decisions.md, and the commands in fasttrack.conf. docs/fasttrack.md "
        "explains the baseline this project starts from.\n\n"
        "Switch on the git hooks once per clone, then run the checks:\n\n"
        "```bash\nscripts/setup.sh\nscripts/check.sh\n```\n",
        encoding="utf-8",
    )
PY

bash scripts/setup.sh

cat <<EOF

bootstrap: $name is set up for $stack.

Next:
  1. Read fasttrack.conf and adjust the commands to your project.
  2. Fill in "Sources of truth" and "When to ask" in AGENTS.md.
  3. Add your stack's setup step to .github/workflows/ci.yml (marked there).
  4. On GitHub, protect the default branch: require the ci check and one review.
  5. Commit on a branch, push, and open a pull request.
EOF
