"""hooks/locate.py 的单元测试：路径抽取和按对话记录分级。

运行：py -3 -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
import locate  # noqa: E402

HOME = os.path.normpath("C:/Users/me") if os.name == "nt" else "/home/me"


def tool_use(tid, name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(tid, error=False):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "is_error": error}]}}


def iso(t):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")


def human(text):
    return {"type": "user", "message": {"content": text}}


@unittest.skipUnless(os.name == "nt", "路径写法按 Windows 本机")
class PathsInTextTest(unittest.TestCase):
    def paths(self, text):
        return locate.paths_in_text(text, HOME)

    def test_home_and_drive_paths(self):
        self.assertEqual(self.paths("cd ~/repo/sub && git status"), [os.path.normpath(HOME + "/repo/sub")])
        self.assertEqual(self.paths(r"type C:\Users\me\a.py, done"), [os.path.normpath(r"C:\Users\me\a.py")])

    def test_git_bash_drive_path(self):
        self.assertEqual(self.paths("ls /c/Users/me/x"), [os.path.normpath("C:/Users/me/x")])

    def test_url_is_not_a_path(self):
        self.assertEqual(self.paths("curl https://api.github.com/a/b"), [])

    def test_quoted_path_keeps_spaces(self):
        self.assertEqual(self.paths('ls "C:/Users/me/Obsidian Vault/03-悬着的事" -l'),
                         [os.path.normpath("C:/Users/me/Obsidian Vault/03-悬着的事")])

    def test_relative_paths_ignored(self):
        self.assertEqual(self.paths("git -C hooks diff tests/x.py"), [])

    def test_esafe_targets_need_apply_and_write_subcommand(self):
        t = locate._esafe_targets
        n = os.path.normpath
        self.assertEqual(t(locate._tokens("esafe-code edit a.py --root C:/r --json --apply"), None, HOME), [n("C:/r/a.py")])
        self.assertEqual(t(locate._tokens("esafe-code edit a.py --root C:/r --json"), None, HOME), [])
        self.assertEqual(t(locate._tokens("esafe-code read a.py --root C:/r --apply"), None, HOME), [])


@unittest.skipUnless(os.name == "nt", "路径写法按 Windows 本机")
class TouchedTest(unittest.TestCase):
    def test_kinds_and_success_only(self):
        rows = [
            tool_use("1", "Write", file_path="C:/p/a.py"), result("1"),
            tool_use("2", "Edit", file_path="C:/p/b.py"), result("2", error=True),
            tool_use("3", "Read", file_path="C:/q/docs/HANDOFF.md"), result("3"),
            tool_use("4", "Bash", command="py -3 C:/r/gen.py"), result("4"),
            tool_use("5", "Bash", command="esafe-code edit x.py --root C:/s --apply"), result("5"),
            tool_use("6", "Bash", command="esafe-code edit x.py --root C:/t --apply"),
        ]
        got = locate.touched(rows, 0, HOME)
        n = os.path.normpath
        self.assertEqual(got, [("write", n("C:/p/a.py")),
                               ("read", n("C:/q/docs/HANDOFF.md")),
                               ("shell", n("C:/r/gen.py")),
                               ("write", n("C:/s/x.py")), ("shell", n("C:/s")),
                               ("shell", n("C:/t"))])

    def test_esafe_only_target_is_write(self):
        cmd = ("cd C:/repo && py -3 C:/tools/esafe_code.py edit hooks/a.py --expected-sha256 abc "
               "--edits-file C:/tmp/e.json --root C:/repo --json --apply")
        got = dict((p, k) for k, p in locate.touched([tool_use("1", "Bash", command=cmd), result("1")], 0, HOME))
        n = os.path.normpath
        self.assertEqual(got[n("C:/repo/hooks/a.py")], "write")
        for other in ("C:/tools/esafe_code.py", "C:/tmp/e.json", "C:/repo"):
            self.assertEqual(got[n(other)], "shell")

    def test_shell_paths_never_promoted_by_mtime(self):
        # 修改时间是弱证据：恰好在命令执行期间被别处改过的文件，只读命令也不能升为写入
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "HANDOFF.md"
            f.write_text("x", encoding="utf-8")
            t0 = f.stat().st_mtime
            call = tool_use("1", "Bash", command=f"echo {f}")
            call["timestamp"] = iso(t0 - 1)
            res = result("1")
            res["timestamp"] = iso(t0 + 1)
            self.assertEqual(locate.touched([call, res], 0, HOME), [("shell", str(f))])

    def test_start_limits_to_turn(self):
        rows = [tool_use("1", "Write", file_path="C:/old.py"), result("1"), human("下一件"),
                tool_use("2", "Write", file_path="C:/new.py"), result("2")]
        start = locate.last_prompt_index(rows)
        self.assertEqual(locate.touched(rows, start, HOME), [("write", os.path.normpath("C:/new.py"))])


class WorktreeMovesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "main/.git").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def moves(self, *commands, name="Bash", cwd=None):
        rows = []
        for i, c in enumerate(commands):
            rows += [tool_use(str(i), name, command=c), result(str(i))]
        return locate.worktree_moves(rows, cwd, HOME)

    def test_relative_path_after_cd(self):
        mv = self.moves(f"cd {self.root / 'main'} && git worktree add -b feat/x ../main-wt-x HEAD 2>&1")
        self.assertEqual(mv, {os.path.normcase(str(self.root / "main-wt-x")): self.root / "main"})

    def test_git_dash_c_and_options_before_path(self):
        mv = self.moves(f'git -C "{self.root / "main"}" worktree add -q --detach "{self.root / "wt" / "a b"}" HEAD')
        self.assertEqual(list(mv.values()), [self.root / "main"])
        self.assertIn(os.path.normcase(str(self.root / "wt" / "a b")), mv)

    def test_powershell_backslash_paths(self):
        main, wt = str(self.root / "main"), str(self.root / "main-wt" / "fix")
        mv = self.moves(f"cd {main}; git worktree add -b fix/y {wt} master", name="PowerShell")
        self.assertEqual(mv, {os.path.normcase(wt): self.root / "main"})

    def test_cwd_used_when_no_cd(self):
        mv = self.moves("git worktree add .worktrees/t -b t", cwd=str(self.root / "main"))
        self.assertIn(os.path.normcase(str(self.root / "main/.worktrees/t")), mv)

    def test_cd_options_resolved_or_mapping_skipped(self):
        main = self.root / "main"
        for cmd in (f"Set-Location -LiteralPath {main}; git worktree add ../wt-a -b a",
                    f"cd -- {main} && git worktree add ../wt-a -b a",
                    f"cd -P {main} && git worktree add ../wt-a -b a"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.moves(cmd, cwd=str(self.root / "elsewhere")),
                                 {os.path.normcase(str(self.root / "wt-a")): main})
        self.assertEqual(self.moves("cd - && git worktree add ../wt-a -b a", cwd=str(main)), {})
        self.assertEqual(self.moves(f"cd -Weird {main} && git worktree add ../wt-a -b a", cwd=str(main)), {})

    def test_failed_add_does_not_override(self):
        (self.root / "other/.git").mkdir(parents=True)
        wt = self.root / "wt"
        ok = f"git -C {self.root / 'main'} worktree add {wt} -b a"
        bad = f"git -C {self.root / 'other'} worktree add {wt} -b b"
        rows = [tool_use("1", "Bash", command=ok), result("1"),
                tool_use("2", "Bash", command=bad), result("2", error=True)]
        self.assertEqual(locate.worktree_moves(rows, None, HOME), {os.path.normcase(str(wt)): self.root / "main"})
        fatal = result("3")
        fatal["message"]["content"][0]["content"] = f"fatal: '{wt}' already exists"
        rows += [tool_use("3", "Bash", command=bad + " 2>&1 | tail -1"), fatal]
        self.assertEqual(locate.worktree_moves(rows, None, HOME), {os.path.normcase(str(wt)): self.root / "main"})
        self.assertEqual(locate.worktree_moves([tool_use("4", "Bash", command=bad)], None, HOME), {})

    def test_printed_command_is_not_executed(self):
        main = self.root / "main"
        self.assertEqual(self.moves(f"echo git -C {main} worktree add {self.root / 'wt'} -b a"), {})
        self.assertEqual(self.moves(f"& git -C {main} worktree add {self.root / 'wt'} -b a", name="PowerShell"),
                         {os.path.normcase(str(self.root / "wt")): main})

    def test_not_a_repo_or_other_git_commands_ignored(self):
        self.assertEqual(self.moves(f"cd {self.root} && git worktree add ../x -b x"), {})
        self.assertEqual(self.moves(f"cd {self.root / 'main'} && git worktree list && git status"), {})

    def test_moved_only_when_worktree_gone(self):
        wt = self.root / "main-wt-x"
        mv = {os.path.normcase(str(wt)): self.root / "main"}
        self.assertEqual(locate.moved(wt / "src" / "a.py", mv), str(self.root / "main" / "src" / "a.py"))
        self.assertIsNone(locate.moved(self.root / "main-wt-xy" / "a.py", mv))
        wt.mkdir()
        self.assertIsNone(locate.moved(wt / "src" / "a.py", mv))
        self.assertIsNone(locate.moved(wt / "a.py", None))


class RepoRootTest(unittest.TestCase):
    def test_finds_git_dir_or_file_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a/.git").mkdir(parents=True)
            (root / "b").mkdir()
            (root / "b/.git").write_text("gitdir: elsewhere", encoding="utf-8")
            (root / "a/src").mkdir()
            self.assertEqual(locate.repo_root(root / "a/src/gone.py"), root / "a")
            self.assertEqual(locate.repo_root(root / "b/x.py"), root / "b")
            self.assertIsNone(locate.repo_root(root / "c/x.py"))
            repos = locate.repos_of([root / "a/x", root / "a/src/y", root / "b/z", root / "c/w"], limit=5)
            self.assertEqual(repos, [root / "a", root / "b"])
            self.assertEqual(locate.repos_of([root / "a/x", root / "b/z"], limit=1), [root / "a"])


if __name__ == "__main__":
    unittest.main()
