# Project conventions

Every session reads this file first, people and agents alike. Each rule
carries its reason, because a rule without one gets treated as taste and
overturned by the next session that finds it inconvenient. The stories
behind the rules live in docs/decisions.md; this file stays short.

## What this project is

<!-- fasttrack:project -->
**fasttrack-template**: a stack-agnostic baseline for any development
project, with the conventions for working with coding agents already in
place. Fork it, run scripts/bootstrap.sh, and start at layer one.
<!-- /fasttrack:project -->

## Sources of truth

One authority per kind of fact:

- Conventions: this file.
- Decisions, their reasons and what would reverse them: docs/decisions.md.
- Which rule is enforced where: docs/enforcement.md.
- The project's commands (lint, tests, test patterns): fasttrack.conf.
- State of work (pull requests, CI, issues): GitHub, read live.
- Facts about the system: the code.

Where this file and a document disagree about a convention, this file wins.
Where they disagree about a fact about the system, the code wins and both
documents are wrong.

## When to ask vs. just do

- Just do: write and run tests, run scripts/check.sh, create a branch,
  commit, push the branch, open a pull request.
- Ask first: destructive git, a new dependency, changes to CI or to
  fasttrack.conf, anything on a protected branch, and anything that leaves
  the repository (deploys, emails, posts).

## No state snapshots

Do not write status files (STATUS.md, FIXES_APPLIED.md, progress notes in
the root). They go stale within a session and nobody reads them, not even
the next session. State lives in GitHub; read it there.

## Shell commands paste as-is

In docs and replies: one command per line, no inline `#` comments, no
prompts (`$`). People paste them, and a comment pasted into a shell fails.

## GitHub workflow

- The agent never merges or closes pull requests. It opens them; the owner
  reads the diff and merges. Speed is not the goal; a reader is.
- Done means the branch is pushed, scripts/check.sh is green, and the pull
  request is open. Open it without asking.
- Never add commits to a branch after its pull request has merged. They
  reach nobody. Start a new branch from the default branch.
- A pull request's state is read, not remembered. Check GitHub before
  saying what is merged, open or green.
- Assign every pull request to the owner (OWNER in fasttrack.conf), so it
  shows up in their review list rather than as a link in chat.
- The agent never deletes branches (docs/decisions.md, DEC-2).

## Commits

- Subject in the imperative, under 70 characters: "Add parser", not
  "Added parser". A body after a blank line says why; the diff shows what.
- No model name in the message text. It dates the artifact and says
  nothing about whether the change is right. A Co-Authored-By trailer may
  carry it.
- Never amend or force-push a commit that is already pushed. Add a new one.

## Test first

- Write the test, run it, and see it fail for the right reason. Then write
  the code and see it pass. The reviewable artifact is the red to green
  transition: paste both runs in the pull request.
- Test the property, not the mechanism: what the user gets, not how the
  code does it. A test that passes whether or not the code works is worse
  than no test.
- Bites enforces this: every test file a branch adds must fail on the code
  before the change. A test that pins behaviour that already exists is
  named in a commit message line, one test per line:
  `Characterises: path/to/test_file`.
- Keep it proportionate. Test where a bug would silently corrupt results;
  do not build a harness for a five-line script.

## Mechanisms, not prose

- An incident produces a hook, a test or a repository setting. A paragraph
  here only when none is possible, and the paragraph says why.
- tools/guard.py holds every rule a machine can check. Git hooks, the
  agent hook and CI all call it. A refusal starts with `guard:` and names
  its rule: follow the rule, do not look for a way around it.
- Never skip the hooks (`--no-verify`). Fix what they report.
- When you add or change a rule, update docs/enforcement.md, including the
  rules that have no mechanism, so nobody thinks they are enforced.
- The guards have their own tests in tools/tests. A rule that stops firing
  turns one of them red.

## Roles and reports

- Split the work when it is more than a small fix: test-author writes the
  failing test, implementer makes it pass, reviewer reads the diff with
  fresh eyes (.claude/agents/). No session grades its own work.
- Reports carry output, not impressions: the command, its exit code and its
  last lines, verbatim. "Tests pass" without output is not a report.
- Name assumptions no test observes in an `Unverified:` paragraph in the
  commit body or the pull request.

## Coach me

- Speak up when something hurts long-term quality, even when the owner
  asked for it. Point at the rule here, so it is a shared standard and not
  an opinion.
- Say so before continuing when you see: a merge within 30 minutes of
  opening, code before a failing test, a finding with no denominator, a
  rule without a mechanism, a report without output.
- At the end of a session, give two or three sentences on what could have
  gone better, or "nothing notable".
- Log a weakness in docs/COACHING.md only when it has been seen twice. Tag
  agent-side entries `[agent]`, so the next session knows its
  predecessors' failure modes.

## Decisions

- Record a decision in docs/decisions.md when it changes how the project
  works, when an alternative was seriously considered, or when the owner
  overrides an objection. Ask the agent to write the entry; review it in the
  pull request like any other change.
- A later session overturns a decision by editing its entry and saying so,
  never by quietly building the other thing.
- To consult the register cheaply, list the headings first:
  `grep -n "^## DEC-" docs/decisions.md`

## Right-size

- Fast checks where you work, every check once in CI before merge. Keep
  FAST_TEST_CMD under a minute.
- Measure what the process costs. Loosen a mechanism that costs more than
  it catches, deliberately, as an amendment in the register.
- When copying these conventions to another project, port the mechanisms,
  not the paragraphs, and name what you left out.
- Start at the bottom. Add a layer only when an incident makes you.
