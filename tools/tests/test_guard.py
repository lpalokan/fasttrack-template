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

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hook_env  # noqa: E402,F401  (drops the variables that would aim git at the real repository)
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
            "gh pr view 12",
            "git branch new-feature",
            "git log --oneline -n 5",
            "echo 'git push --force is refused'",
            "grep -n 'gh pr merge' docs/enforcement.md",
        ]:
            self.assertAllowed(command)

    def test_quoted_text_is_not_a_command(self):
        self.assertAllowed("git commit -m 'Explain; git branch -D was used' -m 'Why.'")
        self.assertAllowed('gh pr comment 3 --body "Never run gh pr merge yourself"')

    def test_a_dry_run_push_is_allowed(self):
        self.assertAllowed("git push origin main --dry-run")
        self.assertAllowed("git push -n origin main")

    def test_more_ways_to_force_push_are_refused(self):
        for command in [
            "env git push -f",
            "(git push -f)",
            "git --git-dir .git push -f",
            "git push +feature",
        ]:
            self.assertRefused(command, "rewrite pushed work")

    def test_switching_hooks_off_by_config_is_refused(self):
        self.assertRefused("git -c core.hooksPath=/dev/null commit -m 'Add x'", "skip the git hooks")

    def test_amend_checks_the_directory_given_with_C(self):
        with mock.patch.object(guard, "head_is_pushed", return_value=False) as pushed:
            guard.check_agent_call("Bash", {"command": "git -C other/repo commit --amend"}, cwd="/work")
        pushed.assert_called_once_with(os.path.join("/work", "other/repo"))

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
        # Opening one is not a merge; whether it was reviewed is ReviewBeforePullRequest's.
        self.assertNotIn(guard.MERGE, guard.check_agent_call("mcp__github__create_pull_request", {}))


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

    def test_the_verbose_diff_below_the_scissors_is_not_the_message(self):
        scissors = (
            "# ------------------------ >8 ------------------------\n"
            "# Do not modify or remove the line above.\n"
            "diff --git a/x b/x\n+model = 'gpt-4o'\n"
        )
        self.assertEqual(guard.check_commit_message(self.good + scissors), [])
        reasons = guard.check_commit_message("Add parser\n" + scissors)
        self.assertTrue(any("body" in r for r in reasons), reasons)

    def test_a_one_line_body_in_key_value_form_is_still_a_body(self):
        self.assertEqual(guard.check_commit_message("Fix parser\n\nWhy: it dropped negatives.\n"), [])
        reasons = guard.check_commit_message("Add parser\n\nNote: drafted with GPT-4o.\n")
        self.assertTrue(any("model name" in r for r in reasons), reasons)

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


class Repo(unittest.TestCase):
    """A throwaway repository with a bare remote."""

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=cwd or self.repo, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit(self, message, name="f.txt", content=None):
        Path(self.repo, name).write_text(content if content is not None else message)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.remote = root / "remote.git"
        self.repo = root / "work"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("remote", "add", "origin", str(self.remote))

    def tearDown(self):
        self._tmp.cleanup()


class PushedWork(Repo):
    def test_amending_a_really_pushed_commit_is_refused(self):
        self.commit("Add a\n\nWhy.")
        self.git("push", "-q", "origin", "main")
        reasons = guard.check_agent_call("Bash", {"command": "git commit --amend --no-edit"}, cwd=str(self.repo))
        self.assertTrue(any("amend" in r for r in reasons), reasons)
        self.commit("Add b\n\nWhy.", name="b.txt")
        self.assertEqual(
            guard.check_agent_call("Bash", {"command": "git commit --amend --no-edit"}, cwd=str(self.repo)), []
        )

    def test_a_push_that_extends_a_merged_pull_request_is_detected(self):
        merged_head = self.commit("Add a\n\nWhy.")
        later = self.commit("Add b\n\nWhy.", name="b.txt")
        self.assertTrue(guard.extends_merged_head(str(self.repo), later, [merged_head]))

    def test_a_new_branch_that_reuses_a_merged_name_is_not_refused(self):
        self.commit("Add a\n\nWhy.")
        self.git("checkout", "-q", "--orphan", "fresh")
        fresh = self.commit("Start fresh\n\nWhy.", name="c.txt")
        unrelated = "f" * 40
        self.assertFalse(guard.extends_merged_head(str(self.repo), fresh, [unrelated]))


class ReviewBeforePullRequest(Repo):
    """A pull request opens only after the reviewer has read the branch: its last commit says so."""

    REVIEWED = "Add calc\n\nThe owner asked.\n\nReviewed: ready, findings fixed"

    def create(self, command="gh pr create --fill"):
        return guard.check_agent_call("Bash", {"command": command}, cwd=str(self.repo))

    def assertRefused(self, reasons):
        self.assertTrue(any("Reviewed:" in r for r in reasons), reasons)

    def test_a_branch_nobody_reviewed_cannot_open_a_pull_request(self):
        self.git("switch", "-q", "-c", "feature")
        self.commit("Add calc\n\nThe owner asked.")
        self.assertRefused(self.create())

    def test_a_reviewed_branch_can(self):
        self.git("switch", "-q", "-c", "feature")
        self.commit(self.REVIEWED)
        self.assertEqual(self.create(), [])

    def test_a_commit_after_the_review_needs_reviewing_too(self):
        self.git("switch", "-q", "-c", "feature")
        self.commit(self.REVIEWED)
        self.commit("Add sub\n\nAfter the review.", name="g.txt")
        self.assertRefused(self.create())

    def test_the_branch_named_by_head_is_the_one_checked(self):
        self.git("switch", "-q", "-c", "reviewed")
        self.commit(self.REVIEWED)
        self.git("switch", "-q", "-c", "unreviewed")
        self.commit("Add sub\n\nNot reviewed.", name="g.txt")
        self.assertEqual(self.create("gh pr create --head reviewed --fill"), [])
        self.assertRefused(self.create("gh pr create -H unreviewed --fill"))

    def test_the_github_connector_is_held_to_the_same_rule(self):
        self.git("switch", "-q", "-c", "feature")
        self.commit("Add calc\n\nThe owner asked.")
        call = lambda: guard.check_agent_call("mcp__github__create_pull_request",
                                              {"head": "feature", "base": "main", "title": "Add calc"},
                                              cwd=str(self.repo))
        self.assertRefused(call())
        self.commit(self.REVIEWED, name="g.txt")
        self.assertEqual(call(), [])

    def test_the_review_line_counts_as_a_trailer(self):
        body, trailers = guard.split_trailers(
            ["The owner asked.", "", "Reviewed: ready", "Co-Authored-By: A <a@example.com>"])
        self.assertEqual(trailers, ["Reviewed: ready", "Co-Authored-By: A <a@example.com>"])


class EntryPoints(Repo):
    script = str(Path(__file__).resolve().parents[1] / "guard.py")

    def run_guard(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, self.script, *args], cwd=self.repo, input=stdin, capture_output=True, text=True
        )

    def test_pre_push_reads_protected_branches_from_the_conf(self):
        Path(self.repo, "fasttrack.conf").write_text('PROTECTED_BRANCHES="develop"\n')
        line = f"refs/heads/x {'a' * 40} refs/heads/develop {'0' * 40}\n"
        result = self.run_guard("pre-push", "origin", "url", stdin=line)
        self.assertEqual(result.returncode, 1)
        self.assertIn("develop", result.stderr)

    def test_commit_range_names_the_offending_commit(self):
        self.commit("Add a\n\nWhy.")
        base = self.git("rev-parse", "HEAD")
        bad = self.commit("Added b")
        result = self.run_guard("commit-range", f"{base}..HEAD")
        self.assertEqual(result.returncode, 1)
        self.assertIn(bad[:12], result.stderr)


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
        violations, report = self.run_bites()
        self.assertEqual(violations, [])
        self.assertTrue(any("tests/test_sub.py fails on" in line for line in report), report)

    def test_a_path_with_spaces_reaches_the_test_command_whole(self):
        (self.repo / "tests" / "test_with space.py").write_text("x = 1\n")
        self.commit("Add a spaced test\n\nNames happen.")
        violations, _ = guard.bites(str(self.repo), self.base, ["tests/test_*.py"], "test -f {file}")
        self.assertEqual(len(violations), 1, violations)

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


class HookEnvironment(unittest.TestCase):
    """A hook run from a git worktree gets GIT_DIR pointing at the real repository. The tests'
    throwaway repositories must stay throwaway: on 2026-10-25 they set core.bare and the user's
    name in the real repository and committed to its branch."""

    def test_the_tests_leave_the_repository_named_by_git_dir_alone(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "sentinel"

            def git(*args):
                return subprocess.run(["git", *args], cwd=sentinel, env=clean, check=True,
                                      capture_output=True, text=True).stdout

            sentinel.mkdir()
            git("init", "-q", "-b", "main")
            git("-c", "user.name=Owner", "-c", "user.email=owner@example.com",
                "commit", "-q", "--allow-empty", "-m", "Start")
            before = (git("config", "--local", "--list"), git("for-each-ref"))
            result = subprocess.run(
                [sys.executable, __file__, "PushedWork.test_amending_a_really_pushed_commit_is_refused"],
                env={**clean, "GIT_DIR": str(sentinel / ".git")}, capture_output=True, text=True,
            )
            after = (git("config", "--local", "--list"), git("for-each-ref"))
        self.assertEqual(after, before, result.stderr[-2000:])
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    @unittest.skipIf(guard.parse_conf(Path(__file__).resolve().parents[2] / "fasttrack.conf").get("BOOTSTRAPPED")
                     == "yes", "the bootstrap tests run only in the template")
    def test_the_bootstrap_tests_run_alone_leave_it_alone_too(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "sentinel"

            def git(*args):
                return subprocess.run(["git", *args], cwd=sentinel, env=clean, check=True,
                                      capture_output=True, text=True).stdout

            sentinel.mkdir()
            git("init", "-q", "-b", "main")
            git("-c", "user.name=Owner", "-c", "user.email=owner@example.com",
                "commit", "-q", "--allow-empty", "-m", "Start")
            before = (git("config", "--local", "--list"), git("for-each-ref"))
            result = subprocess.run(
                [sys.executable, "-m", "unittest", str(Path(__file__).with_name("test_bootstrap.py"))],
                cwd=Path(__file__).resolve().parents[2],
                env={**clean, "GIT_DIR": str(sentinel / ".git")}, capture_output=True, text=True,
            )
            after = (git("config", "--local", "--list"), git("for-each-ref"))
        self.assertEqual(after, before, result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
