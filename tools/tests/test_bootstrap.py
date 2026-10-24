"""Tests for scripts/bootstrap.sh, run against a throwaway copy of the template."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guard  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[2]


def run(cmd, cwd, check=True):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


class TemplateCopy(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "project"
        shutil.copytree(
            TEMPLATE, self.repo, ignore=shutil.ignore_patterns(".git", "__pycache__")
        )
        # In a project that was already bootstrapped, the template's README
        # lives in docs/fasttrack.md; put it back so the copy is a template.
        moved = self.repo / "docs" / "fasttrack.md"
        if moved.exists():
            shutil.copy(moved, self.repo / "README.md")
            moved.unlink()
        run(["git", "init", "-q", "-b", "main"], self.repo)
        run(["git", "add", "-A"], self.repo)

    def tearDown(self):
        self._tmp.cleanup()

    def bootstrap(self, *args, cwd=None):
        return run(["bash", "scripts/bootstrap.sh", *args], cwd or self.repo, check=False)


class FreshFork(TemplateCopy):
    def test_a_stack_preset_fills_the_config(self):
        result = self.bootstrap(
            "--name", "trip-log", "--description", "Logs business trips.",
            "--owner", "someone", "--stack", "go", "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        conf = guard.parse_conf(self.repo / "fasttrack.conf")
        self.assertEqual(conf["PROJECT_NAME"], "trip-log")
        self.assertEqual(conf["OWNER"], "someone")
        self.assertEqual(conf["TEST_CMD"], "go test ./{dir}")
        self.assertEqual(conf["TEST_PATTERNS"], "*_test.go")
        self.assertEqual(conf["BOOTSTRAPPED"], "yes")

    def test_the_project_is_described_where_every_session_reads_it(self):
        self.bootstrap(
            "--name", "trip-log", "--description", "Logs business trips.",
            "--owner", "someone", "--stack", "python", "--yes",
        )
        agents = (self.repo / "AGENTS.md").read_text()
        self.assertIn("trip-log", agents)
        self.assertIn("Logs business trips.", agents)
        self.assertNotIn("stack-agnostic baseline", agents.split("<!-- /fasttrack:project -->")[0])

    def test_the_template_readme_moves_aside(self):
        self.bootstrap(
            "--name", "trip-log", "--description", "Logs business trips.",
            "--owner", "someone", "--stack", "none", "--yes",
        )
        self.assertTrue((self.repo / "docs" / "fasttrack.md").exists())
        self.assertTrue((self.repo / "README.md").read_text().startswith("# trip-log"))

    def test_the_decision_is_recorded(self):
        self.bootstrap(
            "--name", "trip-log", "--description", "Logs business trips.",
            "--owner", "someone", "--stack", "node", "--yes",
        )
        self.assertIn("bootstrapped for trip-log", (self.repo / "docs" / "decisions.md").read_text())

    def test_the_git_hooks_are_switched_on(self):
        self.bootstrap(
            "--name", "trip-log", "--description", "Logs business trips.",
            "--owner", "someone", "--stack", "rust", "--yes",
        )
        hooks = run(["git", "config", "core.hooksPath"], self.repo).stdout.strip()
        self.assertEqual(hooks, ".githooks")

    def test_custom_commands_override_the_preset(self):
        self.bootstrap(
            "--name", "x", "--description", "X.", "--owner", "o", "--stack", "other",
            "--test-cmd", "make test FILE={file}", "--test-patterns", "spec/*_spec.rb",
            "--fast", "make test-fast", "--yes",
        )
        conf = guard.parse_conf(self.repo / "fasttrack.conf")
        self.assertEqual(conf["TEST_CMD"], "make test FILE={file}")
        self.assertEqual(conf["TEST_PATTERNS"], "spec/*_spec.rb")
        self.assertEqual(conf["FAST_TEST_CMD"], "make test-fast")

    def test_an_unknown_stack_is_refused(self):
        result = self.bootstrap("--name", "x", "--description", "X.", "--owner", "o", "--stack", "cobol", "--yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stack", result.stderr)


class ExistingProject(TemplateCopy):
    def test_into_copies_the_baseline_without_overwriting(self):
        target = self.root / "existing"
        target.mkdir()
        run(["git", "init", "-q", "-b", "main"], target)
        (target / "README.md").write_text("# Existing\n")
        (target / "AGENTS.md").write_text("# Our own rules\n")

        result = self.bootstrap(
            "--into", str(target), "--name", "existing", "--description", "Already here.",
            "--owner", "o", "--stack", "python", "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((target / "README.md").read_text(), "# Existing\n")
        self.assertEqual((target / "AGENTS.md").read_text(), "# Our own rules\n")
        self.assertIn("AGENTS.md", result.stdout)
        self.assertTrue((target / "tools" / "guard.py").exists())
        self.assertTrue((target / "docs" / "fasttrack.md").exists())
        self.assertEqual(guard.parse_conf(target / "fasttrack.conf")["PROJECT_NAME"], "existing")


if __name__ == "__main__":
    unittest.main()
