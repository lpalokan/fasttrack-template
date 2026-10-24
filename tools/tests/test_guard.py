"""Tests for tools/guard.py.

The guards are the ground truth for the conventions in AGENTS.md, so they
get tests of their own: a rule that stops firing turns one of these red.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guard  # noqa: E402


def bash(command, **extra):
    return guard.check_agent_call("Bash", {"command": command, **extra})


class AgentHookRefusals(unittest.TestCase):
    def assertRefused(self, command, fragment):
        reasons = bash(command)
        self.assertTrue(reasons, f"expected a refusal for: {command}")
        self.assertTrue(
            any(fragment in r for r in reasons),
            f"no reason mentions {fragment!r}: {reasons}",
        )
        for reason in reasons:
            self.assertTrue(reason.startswith("guard: "), reason)

    def assertAllowed(self, command):
        self.assertEqual(bash(command), [], command)

    def test_skipping_git_hooks_is_refused(self):
        self.assertRefused("git commit --no-verify -m 'Add x'", "skip the git hooks")
        self.assertRefused("git push --no-verify origin feature", "skip the git hooks")
        self.assertRefused("git commit -n -m 'Add x'", "skip the git hooks")

    def test_force_push_is_refused(self):
        self.assertRefused("git push --force origin feature", "rewrite pushed work")
        self.assertRefused("git push -f", "rewrite pushed work")
        self.assertRefused("git push --force-with-lease origin feature", "rewrite pushed work")
        self.assertRefused("git push origin +feature", "rewrite pushed work")

    def test_branch_deletion_is_refused(self):
        self.assertRefused("git branch -D old", "never deletes a branch")
        self.assertRefused("git branch --delete old", "never deletes a branch")
        self.assertRefused("git push origin --delete old", "never deletes a branch")
        self.assertRefused("git push origin :old", "never deletes a branch")

    def test_merging_or_closing_a_pull_request_is_refused(self):
        self.assertRefused("gh pr merge 12 --squash", "never merges")
        self.assertRefused("gh pr close 12", "never merges or closes")

    def test_push_to_a_protected_branch_is_refused(self):
        self.assertRefused("git push origin main", "protected branch")
        self.assertRefused("git push origin HEAD:main", "protected branch")
        self.assertRefused("git push origin feature:refs/heads/master", "protected branch")

    def test_rules_hold_inside_compound_commands(self):
        self.assertRefused("cd repo && git push -f", "rewrite pushed work")
        self.assertRefused("git status; gh pr merge 3", "never merges")
        self.assertRefused("git -C ../other branch -D old", "never deletes a branch")

    def test_amending_a_pushed_commit_is_refused(self):
        with mock.patch.object(guard, "head_is_pushed", return_value=True):
            self.assertRefused("git commit --amend --no-edit", "amend a commit that is already pushed")
        with mock.patch.object(guard, "head_is_pushed", return_value=False):
            self.assertAllowed("git commit --amend --no-edit")

    def test_ordinary_work_is_allowed(self):
        for command in [
            "git status",
            "git push -u origin feature",
            "git push origin feature:feature",
            "git commit -m 'Add parser' -m 'Because the input changed.'",
            "gh pr create --fill",
            "gh pr view 12",
            "git branch new-feature",
            "git log --oneline -n 5",
            "echo 'git push --force is refused'",
            "grep -n 'gh pr merge' docs/enforcement.md",
        ]:
            self.assertAllowed(command)

    def test_unparseable_commands_still_get_checked(self):
        self.assertRefused("git push -f 'unterminated", "rewrite pushed work")

    def test_github_connector_merge_and_close_are_refused(self):
        self.assertTrue(guard.check_agent_call("mcp__github__merge_pull_request", {"pullNumber": 3}))
        self.assertTrue(
            guard.check_agent_call("mcp__github__update_pull_request", {"pullNumber": 3, "state": "closed"})
        )
        self.assertEqual(
            guard.check_agent_call("mcp__github__update_pull_request", {"pullNumber": 3, "title": "x"}), []
        )
        self.assertEqual(guard.check_agent_call("mcp__github__create_pull_request", {}), [])


class CommitMessages(unittest.TestCase):
    good = "Add the parser for quarterly figures\n\nThe old one dropped negative values.\n"

    def test_a_good_message_passes(self):
        self.assertEqual(guard.check_commit_message(self.good), [])

    def test_subject_must_be_under_70_characters(self):
        message = "Add " + "x" * 70 + "\n\nWhy.\n"
        self.assertTrue(any("under 70" in r for r in guard.check_commit_message(message)))

    def test_subject_must_be_imperative(self):
        for subject in ["Added parser", "Fixes the parser", "Updating docs"]:
            reasons = guard.check_commit_message(subject + "\n\nWhy.\n")
            self.assertTrue(any("imperative" in r for r in reasons), subject)

    def test_body_must_say_why(self):
        self.assertTrue(any("body" in r for r in guard.check_commit_message("Add parser\n")))
        self.assertTrue(any("body" in r for r in guard.check_commit_message("Add parser\n\n# comment only\n")))

    def test_model_names_stay_out_of_the_text(self):
        message = "Add parser\n\nWritten with Claude Opus 4 and checked by GPT-4o.\n"
        self.assertTrue(any("model name" in r for r in guard.check_commit_message(message)))

    def test_trailers_may_name_the_model(self):
        message = self.good + "\nCo-Authored-By: Claude Opus 4 <noreply@anthropic.com>\n"
        self.assertEqual(guard.check_commit_message(message), [])

    def test_the_word_claude_alone_is_not_a_model_name(self):
        message = "Update CLAUDE.md with the merge rule\n\nClaude kept asking.\n"
        self.assertEqual(guard.check_commit_message(message), [])

    def test_merge_revert_and_fixup_commits_are_exempt(self):
        for subject in ["Merge branch 'main' into feature", "Revert \"Add parser\"", "fixup! Add parser"]:
            self.assertEqual(guard.check_commit_message(subject + "\n"), [], subject)


class PushUpdates(unittest.TestCase):
    zero = "0" * 40
    sha = "a" * 40

    def test_push_to_protected_branch_is_refused(self):
        lines = [f"refs/heads/main {self.sha} refs/heads/main {self.zero}"]
        self.assertTrue(guard.check_push_updates(lines, ["main"]))

    def test_push_to_feature_branch_is_allowed(self):
        lines = [f"refs/heads/feature {self.sha} refs/heads/feature {self.zero}"]
        self.assertEqual(guard.check_push_updates(lines, ["main"]), [])


class Characterises(unittest.TestCase):
    def test_each_line_names_one_test(self):
        messages = [
            "Pin rounding\n\nCharacterises: tests/test_round.py::test_half_up\n",
            "Pin dates\n\nCharacterises: tests/test_dates.py\nCharacterises: tests/test_tz.py\n",
        ]
        self.assertEqual(
            guard.characterised(messages),
            {"tests/test_round.py", "tests/test_dates.py", "tests/test_tz.py"},
        )

    def test_one_line_cannot_exempt_several_tests(self):
        messages = ["Pin things\n\nCharacterises: tests/test_a.py tests/test_b.py\n"]
        self.assertEqual(guard.characterised(messages), set())


class Conf(unittest.TestCase):
    def test_reads_the_shell_style_config(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "fasttrack.conf")
            path.write_text(
                textwrap.dedent(
                    """\
                    # comment
                    TEST_CMD="python3 -m pytest -q {file}"
                    TEST_PATTERNS='tests/*test_*.py'
                    EMPTY=
                    """
                )
            )
            conf = guard.parse_conf(path)
        self.assertEqual(conf["TEST_CMD"], "python3 -m pytest -q {file}")
        self.assertEqual(conf["TEST_PATTERNS"], "tests/*test_*.py")
        self.assertEqual(conf["EMPTY"], "")

    def test_the_conf_command_prints_one_value(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            Path(d, "fasttrack.conf").write_text('FAST_TEST_CMD="pytest -m "not slow""\n')
            result = subprocess.run(
                [sys.executable, str(Path(guard.__file__)), "conf", "FAST_TEST_CMD"],
                cwd=d, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'pytest -m "not slow"\n')


class Bites(unittest.TestCase):
    """Bites against a real throwaway repository."""

    test_cmd = sys.executable + " -m unittest {file}"

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        (self.repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
        self.commit("Add calc\n\nBase.")
        self.base = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        (self.repo / "tests").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def add_test(self, name, body):
        (self.repo / "tests" / name).write_text(
            "import unittest\nimport calc\n\n\nclass T(unittest.TestCase):\n" + textwrap.indent(body, "    ")
        )

    def run_bites(self):
        return guard.bites(str(self.repo), self.base, ["tests/test_*.py"], self.test_cmd)

    def test_a_test_that_fails_on_the_old_code_bites(self):
        (self.repo / "calc.py").write_text(
            "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
        )
        self.add_test("test_sub.py", "def test_sub(self):\n    self.assertEqual(calc.sub(3, 1), 2)\n")
        self.commit("Add sub\n\nNeeded for refunds.")
        violations, _ = self.run_bites()
        self.assertEqual(violations, [])

    def test_a_test_that_passes_on_the_old_code_is_refused(self):
        self.add_test("test_add.py", "def test_add(self):\n    self.assertEqual(calc.add(1, 1), 2)\n")
        self.commit("Add a test for add\n\nCoverage.")
        violations, _ = self.run_bites()
        self.assertEqual(len(violations), 1)
        self.assertIn("tests/test_add.py", violations[0])

    def test_characterises_names_the_way_past(self):
        self.add_test("test_add.py", "def test_add(self):\n    self.assertEqual(calc.add(1, 1), 2)\n")
        self.commit("Pin add\n\nThe behaviour is right.\n\nCharacterises: tests/test_add.py")
        violations, _ = self.run_bites()
        self.assertEqual(violations, [])

    def test_no_new_tests_means_nothing_to_check(self):
        (self.repo / "README").write_text("hello\n")
        self.commit("Add readme\n\nFor people.")
        violations, report = self.run_bites()
        self.assertEqual(violations, [])
        self.assertTrue(any("no new test files" in line for line in report))

    def test_the_worktree_is_cleaned_up(self):
        self.add_test("test_add.py", "def test_add(self):\n    self.assertEqual(calc.add(1, 1), 2)\n")
        self.commit("Add a test\n\nCoverage.")
        self.run_bites()
        listing = subprocess.run(
            ["git", "worktree", "list"], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout
        self.assertEqual(len(listing.strip().splitlines()), 1, listing)


class AgentHookEntryPoint(unittest.TestCase):
    """The hook protocol: JSON on stdin, exit code 2 and a reason on stderr."""

    script = str(Path(__file__).resolve().parents[1] / "guard.py")

    def run_hook(self, payload):
        return subprocess.run(
            [sys.executable, self.script, "agent-hook"],
            input=payload,
            capture_output=True,
            text=True,
            env={**os.environ},
        )

    def test_refusal_exits_2_with_the_rule(self):
        result = self.run_hook('{"tool_name": "Bash", "tool_input": {"command": "gh pr merge 1"}}')
        self.assertEqual(result.returncode, 2)
        self.assertIn("guard: ", result.stderr)

    def test_allowed_call_exits_0(self):
        result = self.run_hook('{"tool_name": "Bash", "tool_input": {"command": "git status"}}')
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
