---
name: bootstrap
description: Set up a fresh fork of the fasttrack template, or add the baseline to an existing repository, for one specific project. Interviews the owner, runs scripts/bootstrap.sh, fills in the project-specific parts of AGENTS.md and CI, and opens a pull request. Use when the user says bootstrap, set up this template, start a new project from this repository, or add fasttrack to a project.
---
# Bootstrap a project

The goal: a repository where every layer of the baseline works for this
project's stack on the first push, and where AGENTS.md describes this
project rather than the template.

## 1. Look before asking

- Read fasttrack.conf. If `BOOTSTRAPPED="yes"`, say so and ask whether to
  run it again before going on.
- Detect what you can: pyproject.toml or requirements.txt (python),
  package.json (node, and its lint and test scripts), go.mod (go),
  Cargo.toml (rust). Look at where existing tests live.
- If the owner wants the baseline added to another, existing repository,
  you will use `--into <path>`.

## 2. Ask once, in one message

Propose what you detected and ask only for what you could not:

1. The project's name, and what it is in one or two sentences.
2. The stack, and for an unusual one: the lint command, a fast test command
   that runs in under a minute, the full test command, a command that runs
   one test file, and where test files live.
3. The GitHub handle of the person who merges.
4. Where the truth lives for this project: requirements, designs, figures,
   vendor documentation. One authority per kind of fact.
5. What must always be asked about first, beyond the defaults in AGENTS.md.

## 3. Run the script

With the answers, run scripts/bootstrap.sh with `--yes`, for example:

```bash
scripts/bootstrap.sh --name trip-log --description "Logs business trips for tax reports." --owner octocat --stack python --yes
```

For another stack, pass `--stack other` with `--lint`, `--fast`, `--full`,
`--test-cmd` and `--test-patterns`. Paste the script's output.

## 4. Fill in what a script cannot guess

- AGENTS.md, "Sources of truth": add the project's own authorities from
  question 4, keeping the precedence rule.
- AGENTS.md, "When to ask vs. just do": add the owner's answers from
  question 5, each with its reason.
- .github/workflows/ci.yml: add the stack's setup and install steps at the
  marked place.
- If the project already has tests, check that TEST_PATTERNS matches them
  and that TEST_CMD runs one of them.

## 5. Prove it works

- Run `scripts/check.sh` and paste its last lines. If no project checks
  exist yet, say so plainly.
- Run `python3 tools/guard.py conf TEST_CMD` and run that command on one
  existing test file, if there is one.

## 6. Hand it over

- Commit on a new branch with a message that says why, push, and open a pull
  request assigned to the owner. Do not merge it.
- Tell the owner the settings only they can change on GitHub: protect the
  default branch (require the ci check and one review), turn on automatic
  deletion of merged branches (docs/decisions.md, DEC-2), and, if this
  repository should itself be a template, Settings, General, Template
  repository.
