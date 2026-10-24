<!-- fasttrack:template-readme -->
# fasttrack-template

A baseline for any development project, in any language, with the
conventions for working with coding agents already in place. Fork it, run
one command, and start with the practices that usually take months and a
string of incidents to arrive at.

It comes from the webinar *From Prompt to Process*: eight layers, each added
because the one below it was not enough. Here they are already wired up, so
the rules fire on their own instead of depending on anyone's memory.

## What is already in place

| Layer | The rule | What does it here |
|---|---|---|
| 1. Write it down | Conventions live in a file every session reads, not in chat | AGENTS.md (with CLAUDE.md as a thin pointer) |
| 2. Record why | Every decision keeps its reason and what would reverse it | docs/decisions.md, with an entry template |
| 3. The human owns the merge | The agent opens pull requests; a person reads and merges | Deny list in .claude/settings.json, agent hook, pre-push hook |
| 4. Test first | A test must be seen to fail before it counts | Bites: new tests must fail on the old code, in pre-push and CI |
| 5. Mechanisms, not prose | An incident becomes a hook, a test or a setting | tools/guard.py, called by git hooks, the agent hook and CI; docs/enforcement.md |
| 6. Split roles | No session grades its own work; reports carry output | .claude/agents/: test-author, implementer, reviewer, editor |
| 7. Coach both sides | The agent pushes back, and repeated weaknesses are logged | "Coach me" in AGENTS.md; docs/COACHING.md |
| 8. Right-size | Fast checks where you work, every check once in CI | scripts/check.sh with `--fast`; fasttrack.conf |

## Start a new project

1. On GitHub, choose **Use this template** (or fork), then clone your copy.
2. Bootstrap it for your project. Either way works:
   - In Claude Code, type `/bootstrap`. It asks about the project, runs the
     script, fills in the parts a script cannot guess, and opens a pull
     request.
   - In a terminal, run the script and answer its questions:

     ```bash
     scripts/bootstrap.sh
     ```

     Or pass everything at once:

     ```bash
     scripts/bootstrap.sh --name trip-log --description "Logs business trips for tax reports." --owner octocat --stack python --yes
     ```

3. On GitHub, protect the default branch: require the `ci` check and one
   review. This is the one boundary the agent cannot talk its way past.
4. Optionally turn on automatic deletion of merged branches, so stale
   branches do not pile up (docs/decisions.md, DEC-2).

Stacks with presets: `python`, `node`, `go`, `rust`. Any other stack works
with `--stack other` and your own commands; see `scripts/bootstrap.sh
--help`.

## Add it to an existing project

Clone this template next to your project and copy the baseline in. Files you
already have are never overwritten; the script lists them so you can merge by
hand.

```bash
git clone https://github.com/lpalokan/fasttrack-template ../fasttrack-template
../fasttrack-template/scripts/bootstrap.sh --into .
```

## Requirements

- git and bash. On Windows, use Git Bash or WSL.
- Python 3.8 or later, standard library only. The guard is written in
  Python so one implementation serves every stack (docs/decisions.md,
  DEC-3). Your project does not need to use Python.
- Optional: the GitHub CLI (`gh`), signed in. With it, the pre-push hook
  also refuses commits to a branch whose pull request has already merged.

## What fires when

| When | What runs | What it checks |
|---|---|---|
| Session start in Claude Code | scripts/setup.sh | Switches on the git hooks in a fresh clone |
| Before each agent command | tools/guard.py agent-hook | No merge or close, no branch deletion, no force push, no `--no-verify`, no amending pushed work, no push to a protected branch |
| `git commit` | commit-msg hook | Imperative subject under 70 characters, a body that says why, no model name |
| `git push` | pre-push hook | No protected branch, no merged branch, `scripts/check.sh --fast`, bites |
| Pull request | CI | `scripts/check.sh` in full, every commit message, bites |

Every refusal starts with `guard:` and names its rule, so whoever hits it,
person or agent, learns the convention rather than the workaround. The full
list, including the rules that have no mechanism, is in
docs/enforcement.md.

## The commands

All of a project's commands live in fasttrack.conf: lint, fast tests, full
tests, how to run one test file, and where test files live. Everything else
reads them from there, so your laptop, the agent and CI cannot drift apart.

```bash
scripts/setup.sh
scripts/check.sh --fast
scripts/check.sh
scripts/bites.sh
```

## Bites, in one paragraph

For every test file a branch adds, bites checks out the code from before the
change, adds the new test, and runs it. A real test fails there, because the
thing it tests does not exist yet. A test that passes would also pass on code
that does nothing, so the push is refused. When a test is meant to pin
behaviour that already exists, name it in the commit message, one test per
line, and bites lets it through with a record:

```text
Characterises: tests/test_rounding.py
```

## Make it yours

- Start at the bottom. If a layer costs more than it catches in your project,
  loosen it on purpose and record that as an amendment in
  docs/decisions.md, rather than letting it drift.
- When an incident happens, add a hook, a test or a setting, then a line in
  docs/enforcement.md. Add a paragraph to AGENTS.md only when no mechanism
  is possible, and say why.
- Keep AGENTS.md short. Every session reads all of it; the stories belong in
  the decision register.

## Layout

```text
AGENTS.md                      conventions, read by every session and tool
CLAUDE.md                      imports AGENTS.md, adds Claude Code specifics
fasttrack.conf                 the project's commands
docs/decisions.md              decision register
docs/enforcement.md            rule to mechanism table
docs/COACHING.md               repeated weaknesses, both sides
tools/guard.py                 every machine-checkable rule, once
tools/tests/                   the guard's own tests
scripts/bootstrap.sh           set up for a project or copy into one
scripts/setup.sh               switch on the git hooks
scripts/check.sh               the one definition of green
scripts/bites.sh               new tests must fail on the old code
.githooks/                     commit-msg and pre-push
.claude/settings.json          deny list and hooks for Claude Code
.claude/agents/                test-author, implementer, reviewer, editor
.claude/skills/bootstrap/      the /bootstrap skill
.github/workflows/ci.yml       CI: check, commit messages, bites
.github/pull_request_template.md
```

## Licence

MIT, see LICENSE.
