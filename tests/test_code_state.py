"""skills/vibe-flow/scripts/code_state.py 的测试：真 git 仓库 + 真脚本进程。"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "vibe-flow" / "scripts" / "code_state.py"
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid"]


@unittest.skipUnless(shutil.which("git"), "git 不可用")
class CodeStateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="code state 测试-")
        self.root = Path(self._tmp.name)
        subprocess.run(GIT + ["init", "-q"], cwd=self.root, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def commit(self):
        subprocess.run(GIT + ["add", "-A"], cwd=self.root, check=True)
        subprocess.run(GIT + ["commit", "-q", "-m", "base"], cwd=self.root, check=True)

    def state(self, cwd=None):
        proc = subprocess.run([sys.executable, str(SCRIPT), str(cwd or self.root)],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def test_docs_do_not_change_state(self):
        self.write("src/core.py", "a = 1\n")
        self.write("docs/BLUEPRINT.md", "# bp\n")
        self.commit()
        before = self.state()
        self.write("docs/BLUEPRINT.md", "# bp v2\n")
        self.write("docs/HANDOFF.md", "# new\n")
        self.write("tool.CHANGELOG.md", "# sibling\n")
        self.assertEqual(before, self.state())

    def test_tracked_change_and_deletion_change_state(self):
        core = self.write("src/core.py", "a = 1\n")
        self.write("src/other.py", "b = 1\n")
        self.commit()
        base = self.state()
        core.write_text("a = 2\n", encoding="utf-8")
        modified = self.state()
        self.assertNotEqual(base, modified)
        (self.root / "src/other.py").unlink()
        self.assertNotEqual(modified, self.state())

    def test_editing_an_already_dirty_file_changes_state(self):
        core = self.write("src/core.py", "a = 1\n")
        self.commit()
        core.write_text("a = 2\n", encoding="utf-8")
        before = self.state()
        core.write_text("a = 3\n", encoding="utf-8")
        self.assertNotEqual(before, self.state())

    def test_untracked_content_change_is_seen(self):
        self.write("src/core.py", "a = 1\n")
        self.commit()
        new = self.write("src/new.py", "x = 1\n")
        before = self.state()
        new.write_text("x = 2\n", encoding="utf-8")
        self.assertNotEqual(before, self.state())

    def test_works_before_first_commit_and_from_subdir(self):
        self.write("src/core.py", "a = 1\n")
        self.assertEqual(self.state(), self.state(self.root / "src"))

    def test_outside_git_repo_fails(self):
        with tempfile.TemporaryDirectory() as other:
            proc = subprocess.run([sys.executable, str(SCRIPT), other], capture_output=True,
                                  env={**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(other).parent)})
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
