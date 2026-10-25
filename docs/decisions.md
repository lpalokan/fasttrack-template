# Decision register

One numbered entry per decision that changes how this project works. The
rule goes in AGENTS.md; the story, the alternatives and the exit condition
go here, so the instructions file stays short.

Ask the agent to record a decision in this format, then review the entry in
the pull request like any other change. To see what is here without reading
it all:

```bash
grep -n "^## DEC-" docs/decisions.md
```

A later session overturns a decision by editing its entry and saying so,
never by quietly building the other thing. Amendments are dated and made in
place.

| Entry | Status |
|---|---|
| DEC-1 Adopt the fasttrack baseline | Decided |
| DEC-2 The agent never deletes branches | Decided |
| DEC-3 One guard module, three entry points | Decided |
| DEC-4 Model names stay out of commit text | Decided |
| DEC-5 The bootstrap tests run only in the template | Decided |
| DEC-6 A pull request opens only after its review | Decided |

Statuses: Open, Proposed, Decided, Decided by measurement, Amended,
Withdrawn.

## Entry template

```markdown
## DEC-N — <the decision, as one sentence>

Decided YYYY-MM-DD by <who, and how: in conversation, by measurement, by
merging this PR>. Replaces: <earlier rule or entry, if any>.

### What was wrong
The incident, with its date and evidence.

### The decision
What we do now.

### Alternatives rejected
What else was considered, and what each would cost.

### What it costs, stated plainly
The price we accepted.

### What would reverse it
A condition you can observe or measure.

### Unverified
Assumptions no test or observation has confirmed yet.
```

## DEC-1 — Adopt the fasttrack baseline

Decided 2026-10-24 by the template's owner, by creating the template.

### What was wrong
Agent sessions start from zero. Without written conventions, each session
repeated the last one's mistakes: rules lived in chat, merges outran any
reader, tests were never seen to fail, and rules written in prose were
broken on the day they were written.

### The decision
Start every project with the eight layers already in place: an
instructions file, this register, the human owning the merge, test first
with bites, a guard that turns rules into mechanisms, split roles, a
coaching loop, and one check script with a fast and a full speed.

### Alternatives rejected
- Add each layer only after its incident. Cheaper at first, but every
  project pays for the same incidents again.
- A longer instructions file instead of mechanisms. Prose is remembered or
  not; a hook fires.

### What it costs, stated plainly
Some ceremony on small changes, and Python 3 on every machine that runs the
guard.

### What would reverse it
A measured cost per change that the mechanisms do not repay in caught
defects. Loosen the specific mechanism, as an amendment here.

<!-- fasttrack:dec-1-amendments -->

## DEC-2 — The agent never deletes branches

Decided 2026-10-24 by the template's owner.

### What was wrong
An agent cannot see what is checked out on another machine or waiting in
someone's review queue. A deleted branch is somebody else's afternoon.

### The decision
The agent never deletes a branch, local or remote. The agent hook refuses
`git branch -d`, `git push --delete` and `git push origin :branch`.

### Alternatives rejected
- Delete only merged branches. Still needs the agent to judge what is
  "merged" on every remote and machine.

### What it costs, stated plainly
Stale branches accumulate until the owner prunes them.

### What would reverse it
GitHub's automatic delete-on-merge setting, which makes deletion the
platform's job and not the agent's.

## DEC-3 — One guard module, three entry points

Decided 2026-10-24 by the template's owner.

### What was wrong
The same rule written in three places (a git hook, an agent hook, CI)
drifts, and a rule that only exists as prose gets skipped.

### The decision
tools/guard.py holds every machine-checkable rule. Git hooks, the Claude
Code PreToolUse hook and CI call it. It uses only Python's standard
library, so it runs beside any stack. Its own tests live in tools/tests.

### Alternatives rejected
- Shell only. Parsing a tool call's JSON in shell needs jq, which is not
  installed everywhere, and shell is hard to test.
- One implementation per stack. The rules are the same; the copies would
  not stay the same.

### What it costs, stated plainly
Python 3.8 or later must be on every machine that pushes. The agent hook
reads commands as text, so it is a nudge, not a boundary: a determined
workaround (a script that runs the command) passes it. Branch protection on
GitHub is the boundary.

### What would reverse it
A stack where Python cannot be installed. Port the module, not the
paragraphs, and name what was left out.

## DEC-4 — Model names stay out of commit text

Decided 2026-10-24 by the template's owner.

### What was wrong
Model names change every few months; commits last for years. A note saying
which model wrote a change is soon out of date and says nothing about
whether the change is right.

### The decision
The commit-msg hook refuses a model name in the subject or body. A
Co-Authored-By trailer may carry it, because tools can search and filter
trailers.

### What it costs, stated plainly
Agents like to sign their work; the hook will refuse them now and then.

### What would reverse it
A reason to trace changes to models that trailers cannot serve.

## DEC-5 — The bootstrap tests run only in the template

Decided 2026-10-24 by the template's owner, after review of the first
pull request.

### What was wrong
tools/tests/test_bootstrap.py copies the repository and runs
scripts/bootstrap.sh in the copy. In a bootstrapped project the files are
the project's own: a kept AGENTS.md or a moved README failed those tests on
day one, so the pre-push hook refused every push. The tests also copied the
whole working tree, node_modules and build output included, on every push.

### The decision
The bootstrap tests skip themselves when fasttrack.conf says
`BOOTSTRAPPED="yes"`. The guard's own tests still run in every project,
because the hooks there depend on the guard.

### Alternatives rejected
- Delete the bootstrap tests during bootstrap. A project that later updates
  its scripts from the template would lose the tests with no record.
- Make the tests restore the template state first. They would still test
  the project's files, not the template's.

### What it costs, stated plainly
A project that edits its copy of scripts/bootstrap.sh gets no test of that
edit.

### What would reverse it
Projects that keep re-running bootstrap after changing it.

## DEC-6 — A pull request opens only after its review

Decided 2026-10-25 by the template's owner, in conversation, after an
incident in lpalokan/comfy-claude-mcp. Replaces the prose rule in
CLAUDE.md ("Run the reviewer on the branch before opening a pull
request").

### What was wrong
On 2026-10-25 a session in lpalokan/comfy-claude-mcp opened every pull
request (#7 to #13) before its reviewer had read the branch. AGENTS.md
said "Done means ... the pull request is open", and only CLAUDE.md asked
for the review first. Two pull requests merged 36 and 54 seconds after
opening, before their reviews came back; both reviews found real
errors that then needed follow-up pull requests.

### The decision
The agent hook refuses `gh pr create`, and the GitHub connector's create,
unless the last commit of the branch being opened carries a
`Reviewed: <verdict>` trailer. The author adds it after the reviewer's
findings are fixed, in the fix commit or by amending the last commit
while it is unpushed; a commit added after the review needs its own.
AGENTS.md's "Done means" lists the steps in that order, the pull request
template has a Review section, and the reviewer phrases its verdict for
the trailer.

### Alternatives rejected
- Prose only, in AGENTS.md. It was already in CLAUDE.md and did not
  hold for one morning.
- Branch protection requiring an approving review, alone. scripts/
  bootstrap.sh recommends it, and it stays the boundary for people. It
  cannot see the agent's review: the agent opens pull requests from the
  owner's account, an author cannot approve their own pull request, so on
  a one-person repository the owner merges past the requirement as an
  administrator, which is the quick merge this decision is about.
- A file the reviewer writes, checked by the hook. The reviewer is
  read-only by design, and a file in the tree would need cleaning up.

### What it costs, stated plainly
One trailer line per pull request, and a refusal when it is missing.
The trailer is the author's word that a review ran: it stops a
forgotten review, not a skipped one written up as done.

### What would reverse it
Refusals that block legitimate pull requests often (a pull request from
a branch that is not checked out locally, say), or a review step that
moves into CI, where it can be checked rather than declared.

### Unverified
- That `gh pr create` from another directory with `--repo` and a branch
  this clone does not have is rare: the hook refuses it, asking for a
  clone that has the branch.
- Whether lpalokan/comfy-claude-mcp had the review requirement turned on
  when #10 and #13 merged; if so, the owner merged past it.
- That every git in use knows `--end-of-options` (git 2.24 and later).

## Convention history

The incident behind each rule in AGENTS.md, once the rule has one. Add a
line when a rule is added or changed: date, rule, incident, entry.

- 2026-10-25: a pull request opens only after its review (AGENTS.md, 'GitHub
  workflow'). Two pull requests in lpalokan/comfy-claude-mcp merged before
  their reviews came back. DEC-6.
