"""hooks/doc_gate.py 的端到端测试：造假项目 + 假对话记录，跑真实脚本看输出。

运行：py -3 -m unittest discover -s tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "hooks" / "doc_gate.py"
STALE = "停在这批代码改动之前"


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")


def human(text="改一下", at=None):
    row = {"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": text}}
    if at is not None:
        row["timestamp"] = iso(at)
    return row


def notification():
    return {"type": "user", "origin": {"kind": "task-notification"},
            "message": {"role": "user", "content": "<task-notification>fork 完成</task-notification>"}}


_ids = iter(range(10**6))


def edit(path, tool="Edit", ok=True):
    """一次写文件调用 + 它的结果，返回两行记录；成功的调用顺带把文件 mtime 刷到现在，模拟真的写过。"""
    tid = f"toolu_{next(_ids)}"
    call = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": tool, "input": {"file_path": str(path)}}]}}
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": not ok,
         "content": "ok" if ok else "<tool_use_error>String to replace not found</tool_use_error>"}]}}
    if ok and Path(path).exists():
        os.utime(path, None)
    return [call, result]


def set_mtime(path, t):
    os.utime(path, (t, t))


def flatten(rows):
    out = []
    for r in rows:
        out.extend(r if isinstance(r, list) else [r])
    return out


class DocGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.long_ago = time.time() - 3600

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def doc(self, rel, text="# doc"):
        """已经存在很久的文档：mtime 早于本测试里的任何代码改动。"""
        p = self.write(rel, text)
        set_mtime(p, self.long_ago)
        return p

    def run_gate(self, rows, active=False, **extra):
        tr = self.root / "transcript.jsonl"
        tr.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in flatten(rows)), encoding="utf-8")
        # 临时目录外层若恰好是 git 仓库，别让 git 扫描摸上去
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root), GIT_CEILING_DIRECTORIES=str(self.root.parent))
        payload = {"transcript_path": str(tr), "stop_hook_active": active, **extra}
        proc = subprocess.run(
            [sys.executable, str(GATE)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def toolkit(self, with_docs):
        self.write("tk/cli.py", "# 结构: vibe-scripts/toolkit\n")
        core = self.write("tk/core.py", "def f(): pass\n")
        if with_docs:
            self.doc("tk/docs/BLUEPRINT.md", "# bp")
            self.doc("tk/docs/CHANGELOG.md", "# cl")
        return core

    def test_toolkit_missing_docs_blocks(self):
        core = self.toolkit(with_docs=False)
        out = self.run_gate([human(), edit(core)])
        self.assertEqual(out["decision"], "block")
        self.assertIn("BLUEPRINT.md", out["reason"])
        self.assertIn("CHANGELOG.md", out["reason"])

    def test_code_changed_docs_untouched_blocks(self):
        core = self.toolkit(with_docs=True)
        out = self.run_gate([human(), edit(core)])
        self.assertEqual(out["decision"], "block")
        self.assertIn(STALE, out["reason"])
        self.assertIn("fork", out["reason"])

    def test_changelog_touched_passes(self):
        core = self.toolkit(with_docs=True)
        cl = self.root / "tk/docs/CHANGELOG.md"
        self.assertIsNone(self.run_gate([human(), edit(core), edit(cl)]))

    def test_docs_updated_by_fork_count_without_transcript_record(self):
        # fork 的写入在它自己的记录里，主会话看不到；磁盘上文档比代码新就算跟上
        core = self.toolkit(with_docs=True)
        rows = [human(), edit(core), notification()]
        set_mtime(self.root / "tk/docs/CHANGELOG.md", Path(core).stat().st_mtime + 5)
        self.assertIsNone(self.run_gate(rows))

    def test_docs_written_before_later_code_edit_block(self):
        core = self.toolkit(with_docs=True)
        cl = self.root / "tk/docs/CHANGELOG.md"
        rows = [human(), edit(cl), edit(core)]
        now = time.time()
        set_mtime(cl, now - 10)
        set_mtime(core, now)
        self.assertIn(STALE, self.run_gate(rows)["reason"])

    def test_running_subagent_defers(self):
        core = self.toolkit(with_docs=True)
        task = {"task_id": "t1", "task_type": "subagent", "agent_type": "fork", "created_at": iso(time.time())}
        self.assertIsNone(self.run_gate([human(), edit(core)], background_tasks=[task]))
        self.assertIsNotNone(self.run_gate([human(), edit(core), notification()], background_tasks=[]))

    def test_long_running_shell_task_does_not_defer(self):
        # 开发服务器、tail -f 这类后台任务可能永不结束，不能让闸一直不响
        core = self.toolkit(with_docs=True)
        task = {"task_id": "b1", "task_type": "local_bash", "created_at": iso(time.time())}
        self.assertIsNotNone(self.run_gate([human(), edit(core)], background_tasks=[task]))

    def test_failed_changelog_edit_does_not_count(self):
        core = self.toolkit(with_docs=True)
        cl = self.root / "tk/docs/CHANGELOG.md"
        out = self.run_gate([human(), edit(core), edit(cl, ok=False)])
        self.assertIn(STALE, out["reason"])

    def test_failed_code_edit_is_not_a_change(self):
        core = self.toolkit(with_docs=True)
        self.assertIsNone(self.run_gate([human(), edit(core, ok=False)]))

    def test_stop_hook_active_passes(self):
        core = self.toolkit(with_docs=False)
        self.assertIsNone(self.run_gate([human(), edit(core)], active=True))

    def test_edits_before_last_prompt_ignored(self):
        core = self.toolkit(with_docs=True)
        self.assertIsNone(self.run_gate([human("上一轮"), edit(core), human("这一轮只聊天")]))

    def test_unmarked_code_ignored(self):
        c = self.write("fw/src/main.c", "int main(void){return 0;}\n")
        self.doc("fw/docs/CHANGELOG.md", "# 公司仓自己的 changelog")
        self.assertIsNone(self.run_gate([human(), edit(c)]))

    def test_micro_script_ignored(self):
        s = self.write("scripts/tiny.py", "# 结构: vibe-scripts/micro\n")
        self.assertIsNone(self.run_gate([human(), edit(s, "Write")]))

    def test_standard_script_without_any_layout_lists_both_places(self):
        s = self.write("solo/tool.py", "# 结构: vibe-scripts/standard\n")
        out = self.run_gate([human(), edit(s)])
        self.assertIn("位置看不出来", out["reason"])
        self.assertIn("tool.BLUEPRINT.md", out["reason"])
        self.assertIn("docs", out["reason"])

    def test_existing_sibling_docs_kept_when_neighbours_move(self):
        s = self.write("shared/tool.py", "# 结构: vibe-scripts/standard\n")
        self.doc("shared/tool.BLUEPRINT.md")
        self.doc("shared/tool.CHANGELOG.md")
        out = self.run_gate([human(), edit(s)])
        self.assertIn(STALE, out["reason"])
        self.assertNotIn("缺", out["reason"])

    def test_agents_md_marks_own_dir_even_with_test_file(self):
        s = self.write("proj/tool.py", "# 结构: vibe-scripts/standard\n")
        self.write("proj/test_tool.py", "")
        self.write("proj/AGENTS.md", "# proj")
        out = self.run_gate([human(), edit(s)])
        self.assertIn("docs", out["reason"])
        self.assertNotIn("tool.BLUEPRINT.md", out["reason"])
        self.doc("proj/docs/BLUEPRINT.md")
        cl = self.doc("proj/docs/CHANGELOG.md")
        self.assertIsNone(self.run_gate([human(), edit(s), edit(cl)]))

    def test_non_python_neighbour_does_not_decide_layout(self):
        s = self.write("mixed/tool.py", "# 结构: vibe-scripts/standard\n")
        self.write("mixed/other.ps1", "")
        out = self.run_gate([human(), edit(s)])
        self.assertIn("位置看不出来", out["reason"])

    def test_standard_script_uses_sibling_docs(self):
        self.write("scripts/other.py", "print(1)\n")
        s = self.write("scripts/tool.py", "# 结构: vibe-scripts/standard\n")
        out = self.run_gate([human(), edit(s)])
        self.assertIn("tool.BLUEPRINT.md", out["reason"])
        self.doc("scripts/tool.BLUEPRINT.md")
        cl = self.doc("scripts/tool.CHANGELOG.md")
        self.assertIsNone(self.run_gate([human(), edit(s), edit(cl)]))

    def test_vibe_apps_marker_detected(self):
        for name in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(name=name):
                self.write(f"app_{name}/{name}", "## 架构约束（vibe-apps）\n五层")
                api = self.write(f"app_{name}/api/server.py", "")
                out = self.run_gate([human(), edit(api)])
                self.assertEqual(out["decision"], "block")

    def test_handoff_write_does_not_satisfy_gate(self):
        core = self.toolkit(with_docs=True)
        ho = self.write("tk/docs/HANDOFF.md", "# 交接")
        out = self.run_gate([human(), edit(core), edit(ho)])
        self.assertIn(STALE, out["reason"])

    def test_deleted_code_judged_by_its_directory_mtime(self):
        core = self.toolkit(with_docs=True)
        rows = [human(), edit(core, "Write")]
        core.unlink()
        deleted_at = (self.root / "tk").stat().st_mtime
        cl = self.root / "tk/docs/CHANGELOG.md"
        # 先改文档、后删代码：文档早于删除，要拦
        set_mtime(cl, deleted_at - 5)
        self.assertIn(STALE, self.run_gate(rows)["reason"])
        set_mtime(cl, deleted_at + 5)
        self.assertIsNone(self.run_gate(rows))

    # ---------- git 扫描：经 shell / Python 落盘、对话记录里没有的改动 ----------

    def git_repo(self):
        if not shutil.which("git"):
            self.skipTest("git 不可用")
        core = self.toolkit(with_docs=True)
        git = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
        subprocess.run(git + ["init", "-q"], cwd=self.root, check=True)
        subprocess.run(git + ["add", "tk"], cwd=self.root, check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], cwd=self.root, check=True)
        return core

    def test_git_scan_catches_writes_outside_transcript(self):
        core = self.git_repo()
        start = time.time() - 60
        core.write_text("def f(): return 1\n", encoding="utf-8")
        out = self.run_gate([human(at=start)], cwd=str(self.root))
        self.assertIn(STALE, out["reason"])

    def test_git_scan_catches_staged_changes(self):
        core = self.git_repo()
        start = time.time() - 60
        core.write_text("def f(): return 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "tk/core.py"], cwd=self.root, check=True)
        self.assertIn(STALE, self.run_gate([human(at=start)], cwd=str(self.root))["reason"])

    def test_git_scan_catches_shell_deletion(self):
        core = self.git_repo()
        start = time.time() - 60
        core.unlink()
        self.assertIn(STALE, self.run_gate([human(at=start)], cwd=str(self.root))["reason"])

    def test_git_scan_ignores_deletion_before_turn_start(self):
        core = self.git_repo()
        start = time.time() - 60
        core.unlink()
        set_mtime(self.root / "tk", start - 60)
        self.assertIsNone(self.run_gate([human(at=start)], cwd=str(self.root)))

    def test_git_scan_ignores_changes_before_turn_start(self):
        core = self.git_repo()
        start = time.time() - 60
        core.write_text("def f(): return 1\n", encoding="utf-8")
        set_mtime(core, start - 60)
        self.assertIsNone(self.run_gate([human(at=start)], cwd=str(self.root)))

    def test_git_scan_counts_new_code_but_not_output_data(self):
        self.git_repo()
        start = time.time() - 60
        self.write("tk/out.csv", "a,b\n")
        self.assertIsNone(self.run_gate([human(at=start)], cwd=str(self.root)))
        self.write("tk/new_mod.py", "pass\n")
        self.assertIn(STALE, self.run_gate([human(at=start)], cwd=str(self.root))["reason"])

    def test_git_scan_skipped_without_turn_start_or_repo(self):
        core = self.toolkit(with_docs=True)
        core.write_text("changed\n", encoding="utf-8")
        self.assertIsNone(self.run_gate([human()], cwd=str(self.root)))
        self.assertIsNone(self.run_gate([human(at=time.time() - 60)], cwd=str(self.root)))

    def test_bad_transcript_path_passes(self):
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        proc = subprocess.run([sys.executable, str(GATE)],
                              input=json.dumps({"transcript_path": str(self.root / "nope.jsonl")}),
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def _raw_gate(self, payload):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        env["VIBE_FLOW_DOC_GATE_HOME"] = str(self.root)
        return subprocess.run([sys.executable, str(GATE)], input=payload, capture_output=True, env=env)

    def test_raw_utf8_stdin_with_chinese_and_escapes(self):
        # Claude Code 发的是未转义的 UTF-8；Windows 管道默认按 GBK 解码会吃掉 \" 前的反斜杠
        payload = json.dumps({"stop_hook_active": False,
                              "cwd": "C:\\MyProjects\\Kunlun-新架构-debug",
                              "last_assistant_message": "改动见 `a\\b`，结论：\"已放行\"。"},
                             ensure_ascii=False).encode("utf-8")
        proc = self._raw_gate(payload)
        self.assertEqual((proc.returncode, proc.stderr.decode("utf-8", "replace")), (0, ""))

    def test_internal_error_message_is_utf8(self):
        proc = self._raw_gate(b"{")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("内部错误", proc.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
