# Enforcement table

Each rule in AGENTS.md, and where it fires. Rules with no mechanism are
listed too, with the reason, so nobody thinks they are enforced. Update this
table whenever a rule or a mechanism changes.

## Rules with a mechanism

| Rule | Where it fires | Tested in |
|---|---|---|
| No push to a protected branch | pre-push hook; agent hook; branch protection on GitHub (a setting the owner turns on) | test_guard.py: PushUpdates, AgentHookRefusals |
| No commits to a branch whose pull request has merged | pre-push hook, when `gh` is installed and signed in | Not tested: needs GitHub |
| Never skip the hooks (`--no-verify`) | agent hook | AgentHookRefusals |
| Never force-push or amend pushed work | agent hook | AgentHookRefusals |
| The agent never deletes a branch | agent hook, shell and GitHub connector | AgentHookRefusals |
| The agent never merges or closes a pull request | deny list in .claude/settings.json; agent hook; branch protection requiring a review | AgentHookRefusals |
| Commit subject imperative and under 70 characters, a body, no model name | commit-msg hook; CI, for every commit in the pull request | CommitMessages |
| A new test must fail on the old code | bites, in the pre-push hook and in CI | Bites |
| One definition of green | scripts/check.sh: pre-push with `--fast`, CI in full | The guard's own tests run first in every check |
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
