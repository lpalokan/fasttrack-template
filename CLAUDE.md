@AGENTS.md

## Claude Code specifics

AGENTS.md is the one entry point for every tool; this file only adds what is
particular to Claude Code. Keeping a copy here would drift.

- .claude/settings.json runs tools/guard.py before every shell command and
  GitHub connector call, and scripts/setup.sh at the start of every session,
  so the git hooks are on before the first push.
- The deny list in .claude/settings.json blocks merging and closing pull
  requests whatever the prompt says.
- Roles live in .claude/agents/: test-author, implementer, reviewer, editor.
  Run the reviewer on the branch before opening a pull request.
- In a fresh fork, /bootstrap sets the project up.
