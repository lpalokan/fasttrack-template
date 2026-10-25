@AGENTS.md

## Claude Code specifics

AGENTS.md is the one entry point for every tool; this file only adds what is
particular to Claude Code. Keeping a copy here would drift.

- .claude/settings.json runs tools/guard.py before every shell command and
  GitHub connector call, and scripts/setup.sh at the start of every session,
  so the git hooks are on before the first push.
- The deny list in .claude/settings.json blocks merging pull requests,
  through the shell or the GitHub connector, and closing them through the
  shell, whatever the prompt says. The agent hook also refuses closing one
  through the connector.
- Roles live in .claude/agents/: test-author, implementer, reviewer, editor.
- The agent hook refuses opening a pull request, through the shell or the
  GitHub connector, until the branch's last commit carries a `Reviewed:`
  trailer (AGENTS.md, 'GitHub workflow').
- In a fresh fork, /bootstrap sets the project up.
