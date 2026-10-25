# Enforcement table

Each rule in AGENTS.md, and where it fires. Rules with no mechanism are
listed too, with the reason, so nobody thinks they are enforced. Update this
table whenever a rule or a mechanism changes.

## Rules with a mechanism

| Rule | Where it fires | Tested in |
|---|---|---|
| No push to a protected branch | pre-push hook; agent hook; branch protection on GitHub (a setting the owner turns on) | test_guard.py: PushUpdates, AgentHookRefusals |
| No commits to a branch whose pull request has merged | pre-push hook, when `gh` can reach GitHub; it refuses only a push that builds on the merged head | PushedWork (the ancestry check; the GitHub lookup is not tested) |
| Never skip the hooks (`--no-verify`) | agent hook | AgentHookRefusals |
| Never force-push or amend pushed work | agent hook | AgentHookRefusals |
| The agent never deletes a branch | agent hook, shell and GitHub connector | AgentHookRefusals |
| The agent never merges or closes a pull request | deny list in .claude/settings.json; agent hook; branch protection requiring a review | AgentHookRefusals |
| Commit subject imperative and under 70 characters, a body, no model name | commit-msg hook; CI, for every commit in the pull request | CommitMessages |
| A new test must fail on the old code | bites, in the pre-push hook and in CI | Bites |
| One definition of green | scripts/check.sh: pre-push with `--fast`, CI in full | The guard's own tests run first in every check |
| Tests never act on the repository they are checked in | tools/tests/hook_env.py, imported first by every test module there, and scripts/check.sh drop the variables `git rev-parse --local-env-vars` lists, which a hook in a worktree inherits | HookEnvironment, for the test modules; the unset in check.sh is not tested |
| Git hooks are on in every clone | SessionStart hook runs scripts/setup.sh | Not tested |

## Rules with no mechanism

| Rule | What covers it instead | Why there is no mechanism |
|---|---|---|
| A pull request's state is read, not remembered | The reviewer and the coach | Nothing can tell a remembered claim from a checked one |
| Reports carry output | The pull request template asks for the red and green runs; the reviewer | Output is free text |
| Test the property, not the mechanism | The reviewer | Needs judgement |
| No state snapshots | Prose | A file name check would be easy to sidestep and noisy |
| Shell commands paste as-is | Prose | Depends on the docs format; add a check if it bites you |
| Coach me triggers | Prose | The agent's judgement is the mechanism |
| Ask first (destructive git, dependencies, CI and fasttrack.conf changes, anything that leaves the repository) | Prose; the agent hook covers the destructive git it can recognise | "Destructive" and "leaves the repository" need judgement |
| Assign every pull request to the owner | Prose | Depends on the tool that opens the pull request |
| No session grades its own work | The reviewer agent; branch protection requiring a review | Who wrote what is not visible to a hook |
| Name unverified assumptions | The pull request template; the reviewer | Free text |
| Record decisions in the register | The reviewer; the editor agent | Whether something is a decision needs judgement |

## Known limits of the mechanisms

Each of these is a place where a mechanism checks less than its rule says.
Close one when it bites you, and move it to the table above.

- Bites checks that a new test fails on the old code, not why. A syntax
  error, a collection error or "no tests found" also counts as failing.
  AGENTS.md asks for "fail for the right reason"; only the red run in the
  pull request shows the reason.
- Bites runs the old code in a separate checkout. If your tests import the
  project through an installed package (an editable install in a `src`
  layout, for example), the old checkout may import the new code, and bites
  will report real tests as passing on the old code. Point the import path at
  the checkout, or share less through BITES_SHARE.
- The pre-push hook runs the checks and bites on the checked-out HEAD, not
  on the ref being pushed. `git push origin other-branch` checks the wrong
  tree.
- The merged-branch check needs `gh` with access to GitHub's API. Where that
  is blocked, as in some cloud sessions, it allows the push.
- The agent hook reads commands as text. A command run from a script file,
  or written in a form it does not parse, passes. Branch protection is the
  boundary; the hook is a nudge (docs/decisions.md, DEC-3).
