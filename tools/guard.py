#!/usr/bin/env python3
"""One guard module, three entry points.

Every rule in AGENTS.md that a machine can check lives here, once. Three
things call it:

  git hooks     .githooks/commit-msg and .githooks/pre-push
  agent hooks   .claude/settings.json, PreToolUse, before each tool call
  CI            .github/workflows/ci.yml, on a clean machine

Each refusal starts with "guard:" and names its rule, so the person or the
agent on the other end learns the convention rather than the workaround.

Standard library only, Python 3.8 or later, so it runs beside any stack.

Usage:
  guard.py agent-hook              JSON tool call on stdin; exit 2 refuses it
  guard.py commit-msg FILE         check one commit message
  guard.py commit-range RANGE      check every commit message in RANGE
  guard.py pre-push REMOTE URL     ref updates on stdin, as git sends them
  guard.py bites [--base REF]      new tests must fail on the old code
  guard.py conf KEY                print one value from fasttrack.conf
"""

import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NO_VERIFY = (
    "guard: never skip the git hooks (--no-verify). Fix what the hook reports instead. "
    "See AGENTS.md, 'Mechanisms, not prose'."
)
FORCE = (
    "guard: never rewrite pushed work (force push). Add a new commit instead. "
    "See AGENTS.md, 'Commits'."
)
AMEND = (
    "guard: never amend a commit that is already pushed. Add a new commit instead. "
    "See AGENTS.md, 'Commits'."
)
DELETE = (
    "guard: the agent never deletes a branch, local or remote. Leave it for the owner to prune. "
    "See docs/decisions.md, DEC-2."
)
MERGE = (
    "guard: the agent never merges or closes pull requests. Push the branch green, open the "
    "pull request, and the owner reads the diff and merges. See AGENTS.md, 'GitHub workflow'."
)
PROTECTED = (
    "guard: no push to a protected branch ({branch}). Push a feature branch and open a pull "
    "request. See AGENTS.md, 'GitHub workflow'."
)
MERGED_BRANCH = (
    "guard: the pull request for {branch} has already merged, so a new commit there reaches "
    "nobody. Start a new branch from the default branch. See AGENTS.md, 'GitHub workflow'."
)

DEFAULT_PROTECTED = ("main", "master")
ZERO_SHA = "0" * 40


# --- configuration ---------------------------------------------------------


def parse_conf(path):
    """Read fasttrack.conf: shell-style KEY="value" lines, no expansion."""
    conf = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return conf
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        conf[key.strip()] = value
    return conf


def repo_root(cwd=None):
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def load_conf(cwd=None):
    root = repo_root(cwd)
    return parse_conf(Path(root, "fasttrack.conf")) if root else {}


def protected_branches(conf):
    names = conf.get("PROTECTED_BRANCHES", "").split()
    return tuple(names) if names else DEFAULT_PROTECTED


# --- agent hook --------------------------------------------------------------


def split_segments(command):
    """Split a shell command into simple commands. Deliberately naive: it
    over-splits quoted text, which can only add checks, never remove one."""
    return [s for s in re.split(r"&&|\|\||[;|\n]", command) if s.strip()]


def tokenize(segment):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        tokens = tokens[1:]
    if tokens and tokens[0] in ("sudo", "command", "exec", "time"):
        tokens = tokens[1:]
    return tokens


def short_flags(tokens):
    """Letters from clusters like -uf; long options are not included."""
    letters = set()
    for token in tokens:
        if re.fullmatch(r"-[A-Za-z]+", token):
            letters.update(token[1:])
    return letters


def head_is_pushed(cwd=None):
    result = subprocess.run(
        ["git", "branch", "-r", "--contains", "HEAD"], cwd=cwd, capture_output=True, text=True
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def branch_name(ref):
    for prefix in ("refs/heads/",):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def check_git(args, cwd, protected):
    # Skip git's global options: git -C dir, git -c key=value, git --no-pager ...
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c") else 1
    if i >= len(args):
        return []
    sub, rest = args[i], args[i + 1:]
    flags = short_flags(rest)
    reasons = []

    if "--no-verify" in rest or (sub == "commit" and "n" in flags):
        reasons.append(NO_VERIFY)

    if sub == "commit" and "--amend" in rest and head_is_pushed(cwd):
        reasons.append(AMEND)

    if sub == "branch" and ("--delete" in rest or flags & {"d", "D"}):
        reasons.append(DELETE)

    if sub == "push":
        positional = []
        takes_value = ("-o", "--push-option", "--repo", "--receive-pack", "--exec")
        j = 0
        while j < len(rest):
            token = rest[j]
            if token in takes_value:
                j += 2
                continue
            if not token.startswith("-"):
                positional.append(token)
            j += 1
        refspecs = positional[1:]
        forced = (
            "--force" in rest
            or "f" in flags
            or any(t.startswith("--force-with-lease") for t in rest)
            or any(r.startswith("+") for r in refspecs)
        )
        if forced:
            reasons.append(FORCE)
        if "--delete" in rest or "d" in flags or any(r.startswith(":") for r in refspecs):
            reasons.append(DELETE)
        for refspec in refspecs:
            dest = branch_name(refspec.lstrip("+").split(":")[-1])
            if dest in protected:
                reasons.append(PROTECTED.format(branch=dest))
    return reasons


def check_agent_call(tool_name, tool_input, cwd=None, protected=DEFAULT_PROTECTED):
    """Return the refusals for one tool call; an empty list allows it."""
    tool_input = tool_input or {}
    if tool_name == "Bash":
        reasons = []
        for segment in split_segments(tool_input.get("command", "")):
            tokens = tokenize(segment)
            if not tokens:
                continue
            program = os.path.basename(tokens[0])
            if program == "git":
                reasons += check_git(tokens[1:], cwd, protected)
            elif program == "gh" and tokens[1:3] in (["pr", "merge"], ["pr", "close"]):
                reasons.append(MERGE)
        return list(dict.fromkeys(reasons))
    if tool_name.endswith("merge_pull_request"):
        return [MERGE]
    if tool_name.endswith("update_pull_request") and tool_input.get("state") == "closed":
        return [MERGE]
    if "delete_branch" in tool_name or "delete_ref" in tool_name:
        return [DELETE]
    return []


# --- commit messages --------------------------------------------------------

NON_IMPERATIVE = {
    "added", "adds", "adding", "fixed", "fixes", "fixing", "updated", "updates", "updating",
    "removed", "removes", "removing", "changed", "changes", "changing", "created", "creates",
    "creating", "implemented", "implements", "implementing", "refactored", "refactors",
    "refactoring", "moved", "moves", "moving", "renamed", "renames", "renaming", "improved",
    "improves", "improving", "made", "makes", "making", "used", "uses", "using", "bumped",
    "bumps", "bumping", "cleaned", "cleans", "cleaning", "deleted", "deletes", "deleting",
    "introduced", "introduces", "introducing", "ensured", "ensures", "ensuring", "handled",
    "handles", "handling", "allowed", "allows", "allowing", "prevented", "prevents",
    "preventing", "replaced", "replaces", "replacing", "supported", "supports", "supporting",
    "converted", "converts", "converting", "wrote", "writes", "writing", "tested", "tests",
}
EXEMPT_SUBJECTS = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")
MODEL_NAME = re.compile(
    r"\b(?:claude[ -](?:opus|sonnet|haiku|fable|instant|\d)"
    r"|(?:opus|sonnet|haiku|fable)[ -]?\d"
    r"|gpt-?\d\w*|chatgpt|o\d-(?:mini|preview|pro)"
    r"|gemini[ -]?\d|llama[ -]?\d|mistral[ -](?:large|medium|small|\d))",
    re.IGNORECASE,
)
TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: \S")


def split_trailers(body_lines):
    """Return (body, trailers): the last paragraph is trailers if every line is one."""
    paragraphs, current = [], []
    for line in body_lines:
        if line.strip():
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    if paragraphs and all(TRAILER.match(l) for l in paragraphs[-1]):
        return [l for p in paragraphs[:-1] for l in p], paragraphs[-1]
    return [l for p in paragraphs for l in p], []


def check_commit_message(text):
    lines = [l.rstrip() for l in text.splitlines() if not l.startswith("#")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ["guard: the commit message is empty."]
    subject = lines[0]
    if subject.startswith(EXEMPT_SUBJECTS):
        return []
    reasons = []
    if len(subject) >= 70:
        reasons.append(
            f"guard: keep the subject under 70 characters (it has {len(subject)}), "
            "so it reads whole in a log. See AGENTS.md, 'Commits'."
        )
    first = re.sub(r"[^A-Za-z]", "", subject.split()[0]).lower()
    if first in NON_IMPERATIVE:
        reasons.append(
            f"guard: write the subject in the imperative ('Add', not '{subject.split()[0]}'), "
            "as if completing 'this commit will…'. See AGENTS.md, 'Commits'."
        )
    body, _trailers = split_trailers(lines[1:])
    if not body:
        reasons.append(
            "guard: add a body after a blank line that says why the change is needed. "
            "The diff shows what; only the message can say why. See AGENTS.md, 'Commits'."
        )
    match = MODEL_NAME.search("\n".join([subject] + body))
    if match:
        reasons.append(
            f"guard: keep the model name ('{match.group(0)}') out of the message text; it dates "
            "the artifact. A Co-Authored-By trailer may carry it. See AGENTS.md, 'Commits'."
        )
    return reasons


def commit_messages(repo, rev_range):
    result = subprocess.run(
        ["git", "log", "--format=%H%x1f%B%x1e", rev_range],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    pairs = []
    for record in result.stdout.split("\x1e"):
        record = record.strip("\n")
        if record:
            sha, _, message = record.partition("\x1f")
            pairs.append((sha, message))
    return pairs


# --- pushes -----------------------------------------------------------------


def check_push_updates(lines, protected):
    reasons = []
    for line in lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, _local_sha, remote_ref, _remote_sha = parts
        branch = branch_name(remote_ref)
        if branch in protected:
            reasons.append(PROTECTED.format(branch=branch))
    return reasons


def pr_has_merged(branch, cwd=None):
    """True if GitHub shows a merged PR for this branch; None when gh can't tell."""
    if not shutil.which("gh"):
        return None
    result = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--state", "merged", "--json", "number"],
        cwd=cwd, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return bool(json.loads(result.stdout or "[]"))
    except ValueError:
        return None


# --- bites ------------------------------------------------------------------

CHARACTERISES = re.compile(r"^Characterises:\s*(\S+)\s*$", re.MULTILINE)


def characterised(messages):
    """Test files exempted by 'Characterises:' lines, one test per line."""
    names = set()
    for message in messages:
        for match in CHARACTERISES.finditer(message):
            names.add(match.group(1).split("::")[0])
    return names


def git(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check)


def bites(repo, base, patterns, test_cmd, share=(), timeout=600):
    """Run each test file this branch adds against the code at `base`.

    A test that passes there would pass on code that does nothing, so it is a
    violation, unless a commit names it in a 'Characterises:' line.
    Returns (violations, report lines).
    """
    added = git(repo, "diff", "--name-only", "--diff-filter=A", base, "HEAD").stdout.split()
    tests = [f for f in added if any(fnmatch.fnmatch(f, p) for p in patterns)]
    short = base[:12]
    if not tests:
        return [], [f"bites: no new test files since {short}"]

    messages = [m for _sha, m in commit_messages(repo, f"{base}..HEAD")]
    exempt = characterised(messages)
    violations, report = [], []
    # Inside a git hook, GIT_DIR and friends point at this checkout; the old
    # code must not see them.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    tmp = tempfile.mkdtemp(prefix="bites-")
    old = os.path.join(tmp, "old")
    try:
        git(repo, "worktree", "add", "--detach", old, base)
        for path in share:
            source, target = Path(repo, path), Path(old, path)
            if source.exists() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source.resolve())
        for test in tests:
            content = git(repo, "show", f"HEAD:{test}").stdout
            target = Path(old, test)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for test in tests:
            if test in exempt:
                report.append(f"bites: {test} exempt, named in a Characterises: line")
                continue
            command = (
                test_cmd.replace("{file}", test)
                .replace("{dir}", os.path.dirname(test) or ".")
                .replace("{stem}", Path(test).stem)
            )
            try:
                result = subprocess.run(
                    command, shell=True, cwd=old, capture_output=True, text=True,
                    timeout=timeout, env=env,
                )
                passed = result.returncode == 0
            except subprocess.TimeoutExpired:
                passed = False
            if passed:
                violations.append(
                    f"guard: {test} passes on {short}, before the change it was added for. "
                    "A test that cannot fail proves nothing. Make it fail on the old code, or, "
                    "if it pins behaviour that already exists, name it in the commit message: "
                    f"'Characterises: {test}'. See AGENTS.md, 'Test first'."
                )
            else:
                report.append(f"bites: {test} fails on {short}, as it should")
    finally:
        git(repo, "worktree", "remove", "--force", old, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
        git(repo, "worktree", "prune", check=False)
    return violations, report


def default_base(repo, conf):
    if os.environ.get("BITES_BASE"):
        ref = os.environ["BITES_BASE"]
    else:
        ref = "origin/" + conf.get("DEFAULT_BRANCH", "main")
    result = git(repo, "merge-base", ref, "HEAD", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


# --- entry points -----------------------------------------------------------


def fail(reasons, code=1):
    for reason in reasons:
        print(reason, file=sys.stderr)
    return code if reasons else 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    command, args = argv[0], argv[1:]

    if command == "agent-hook":
        try:
            call = json.load(sys.stdin)
        except ValueError:
            print("guard: could not read the tool call; allowing it.", file=sys.stderr)
            return 0
        cwd = call.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
        conf = load_conf(cwd)
        reasons = check_agent_call(
            call.get("tool_name", ""), call.get("tool_input"), cwd, protected_branches(conf)
        )
        return fail(reasons, code=2)

    if command == "conf":
        print(load_conf().get(args[0], ""))
        return 0

    if command == "commit-msg":
        text = Path(args[0]).read_text(encoding="utf-8")
        return fail(check_commit_message(text))

    if command == "commit-range":
        repo = repo_root()
        reasons = []
        for sha, message in commit_messages(repo, args[0]):
            reasons += [f"{sha[:12]}: {r}" for r in check_commit_message(message)]
        return fail(reasons)

    if command == "pre-push":
        conf = load_conf()
        lines = sys.stdin.read().splitlines()
        protected = protected_branches(conf)
        reasons = check_push_updates(lines, protected)
        for line in lines:
            parts = line.split()
            if len(parts) == 4 and parts[1] != ZERO_SHA:
                branch = branch_name(parts[2])
                if branch not in protected and pr_has_merged(branch):
                    reasons.append(MERGED_BRANCH.format(branch=branch))
        return fail(reasons)

    if command == "bites":
        repo = repo_root()
        conf = parse_conf(Path(repo, "fasttrack.conf"))
        test_cmd = conf.get("TEST_CMD", "")
        if not test_cmd:
            print("bites: skipped, TEST_CMD is not set in fasttrack.conf (run scripts/bootstrap.sh)")
            return 0
        base = args[args.index("--base") + 1] if "--base" in args else default_base(repo, conf)
        if not base:
            print("bites: skipped, no base commit to compare with (no origin default branch yet)")
            return 0
        base = git(repo, "rev-parse", base).stdout.strip()
        violations, report = bites(
            repo,
            base,
            conf.get("TEST_PATTERNS", "").split(),
            test_cmd,
            share=conf.get("BITES_SHARE", "").split(),
            timeout=int(conf.get("BITES_TIMEOUT", "600") or 600),
        )
        for line in report:
            print(line)
        return fail(violations)

    print(f"guard: unknown command {command!r}\n\n{__doc__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
