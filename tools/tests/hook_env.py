"""Imported first by every test module here, for its side effect.

A hook run from a git worktree exports GIT_DIR, which would point every git
command in these tests at the real repository instead of their own throwaway
ones. Git lists the variables that locate a repository; none of them may
reach the tests, however a test module is run.
"""

import os
import subprocess

for _name in subprocess.run(["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True,
                            check=True).stdout.split():
    os.environ.pop(_name, None)
