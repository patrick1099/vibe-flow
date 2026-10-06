"""hooks/compact_anchor.py 的端到端测试：造假项目，跑真实脚本看注入内容。

运行：py -3 -m unittest discover -s tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "compact_anchor.py"
_ids = iter(range(10**6))


def call(name, ok=True, **inp):
    """一次工具调用 + 结果，返回两行对话记录。"""
    tid = f"toolu_{next(_ids)}"
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "is_error": not ok}]}}]

HANDOFF = """# 交接 · 2026-09-30

**已谈定**：
- 2026-09-30 · 用户 · 串口：用户开着串口时，AI 也要能同时收发、读记录
- 2026-09-30 · 采纳 codex 建议 · 协议识别：按帧头区分，排除逐字节猜测（误判多）

**在做**：串口解析按钮
**下一步**：补自动识别
"""


class CompactAnchorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_hook(self, cwd, source="compact", rows=None):
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        payload = {"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd)}
        if rows is not None:
            tr = self.root / "transcript.jsonl"
            flat = [r for pair in rows for r in pair]
            tr.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in flat), encoding="utf-8")
            payload["transcript_path"] = str(tr)
        proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload, ensure_ascii=False),
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout.strip():
            return None
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        return out["additionalContext"]

    def test_injects_agreed_section_only(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        ctx = self.run_hook(self.root / "proj")
        self.assertIn("AI 也要能同时收发", ctx)
        self.assertIn("排除逐字节猜测", ctx)
        self.assertNotIn("串口解析按钮", ctx)
        self.assertIn("不等于取消", ctx)

    def test_heading_style_section_recognised(self):
        # 回放实测：AI 自己建 HANDOFF 时写的是 `## 已谈定` 标题
        self.write("proj/docs/HANDOFF.md",
                   "# HANDOFF\n\n## 已谈定\n\n- 2026-09-30 · 用户 · 输出 csv 的列名用中文。\n\n## 在做\n- 别的\n")
        ctx = self.run_hook(self.root / "proj")
        self.assertIn("列名用中文", ctx)
        self.assertNotIn("别的", ctx)
        self.write("proj/docs/HANDOFF.md", "# HANDOFF\n\n## 已谈定\n\n## 在做\n- 别的\n")
        self.assertIsNone(self.run_hook(self.root / "proj"))

    def test_only_on_compact(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        for source in ("startup", "resume", "clear"):
            with self.subTest(source=source):
                self.assertIsNone(self.run_hook(self.root / "proj", source))

    def test_found_from_subdirectory(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        sub = self.root / "proj/src/pkg"
        sub.mkdir(parents=True)
        self.assertIn("AI 也要能同时收发", self.run_hook(sub))

    def test_stops_at_git_root(self):
        self.write("outer/docs/HANDOFF.md", HANDOFF)
        (self.root / "outer/inner/.git").mkdir(parents=True)
        self.assertIsNone(self.run_hook(self.root / "outer/inner"))

    def test_handoff_without_agreed_section_ignored(self):
        self.write("proj/docs/HANDOFF.md", "# 交接\n\n**在做**：别的\n")
        self.assertIsNone(self.run_hook(self.root / "proj"))

    def test_empty_agreed_section_ignored(self):
        self.write("proj/docs/HANDOFF.md", "# 交接\n\n**已谈定**：\n\n**在做**：别的\n")
        self.assertIsNone(self.run_hook(self.root / "proj"))

    def test_unrelated_repo_ignored(self):
        self.write("fw/docs/CHANGELOG.md", "# 公司仓")
        self.write("fw/README.md", "**已谈定**：这不是 HANDOFF")
        self.assertIsNone(self.run_hook(self.root / "fw"))

    def test_sibling_handoffs_all_injected(self):
        self.write("scripts/a.HANDOFF.md", "**已谈定**：\n- 甲约定\n")
        self.write("scripts/b.HANDOFF.md", "**已谈定**：\n- 乙约定\n")
        ctx = self.run_hook(self.root / "scripts")
        self.assertIn("甲约定", ctx)
        self.assertIn("乙约定", ctx)
        self.assertIn("只约束脚本 a", ctx)
        self.assertIn("只约束脚本 b", ctx)
        self.assertIn("只对照当前任务涉及的那份", ctx)

    def test_needs_hint_when_present(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        self.write("proj/docs/NEEDS.md", "# NEEDS\n\n## 当前需求区\n")
        self.assertIn("NEEDS.md 的当前需求区", self.run_hook(self.root / "proj"))

    def test_needs_only_project_still_reminded(self):
        # §4 允许已写进 NEEDS 的不再记 HANDOFF，只有 NEEDS 时也要提醒读回
        self.write("proj/docs/NEEDS.md", "# NEEDS\n\n## 当前需求区\n### 第一版非做不可\n- 甲\n")
        (self.root / "proj/src").mkdir()
        ctx = self.run_hook(self.root / "proj/src")
        self.assertIn("NEEDS.md 的当前需求区", ctx)
        self.assertNotIn("以下面为准", ctx)

    def test_unrelated_needs_file_ignored(self):
        self.write("fw/docs/NEEDS.md", "# 客户需求清单\n- 485 通信\n")
        self.assertIsNone(self.run_hook(self.root / "fw"))

    def test_heading_section_keeps_subheadings_and_bold_items(self):
        self.write("proj/docs/HANDOFF.md",
                   "# 交接\n\n## 已谈定\n\n### 核心目标\n- 甲目标\n\n**硬约束**：乙约束\n- 丙条件\n\n## 在做\n- 别的\n")
        ctx = self.run_hook(self.root / "proj")
        for s in ("甲目标", "乙约束", "丙条件"):
            self.assertIn(s, ctx)
        self.assertNotIn("别的", ctx)
        self.write("proj/docs/HANDOFF.md", "# 交接\n\n## 已谈定\n### 核心目标\n- 甲目标\n")
        self.assertIn("甲目标", self.run_hook(self.root / "proj"))

    def test_long_section_lists_paths_without_truncating(self):
        items = "\n".join(f"- 2026-09-30 · 用户 · 事项{i}：" + "很长的约定" * 20 for i in range(60))
        ho = self.write("proj/docs/HANDOFF.md", "**已谈定**：\n" + items + "\n")
        ctx = self.run_hook(self.root / "proj")
        self.assertIn(str(ho), ctx)
        self.assertIn("完整读完", ctx)
        self.assertNotIn("事项0", ctx)

    # ---------- 按对话记录定位：会话开在别处，用绝对路径改项目 ----------

    def fw(self):
        fw = self.root / "fw"
        (fw / ".git").mkdir(parents=True, exist_ok=True)
        return fw

    def test_written_project_injected_when_cwd_is_elsewhere(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        code = self.write("proj/src/a.py")
        self.assertIsNone(self.run_hook(self.fw()))
        ctx = self.run_hook(self.fw(), rows=[call("Write", file_path=str(code))])
        self.assertIn("AI 也要能同时收发", ctx)

    def test_failed_write_does_not_count(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        code = self.write("proj/src/a.py")
        ctx = self.run_hook(self.fw(), rows=[call("Edit", ok=False, file_path=str(code))])
        self.assertIsNone(ctx)

    def test_handoff_read_directly_is_injected(self):
        ho = self.write("proj/docs/HANDOFF.md", HANDOFF)
        ctx = self.run_hook(self.fw(), rows=[call("Read", file_path=str(ho))])
        self.assertIn("AI 也要能同时收发", ctx)

    def test_esafe_apply_counts_as_write(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        cmd = f'py -3 esafe_code.py edit src/a.py --root "{self.root / "proj"}" --json --apply'
        self.assertIn("AI 也要能同时收发", self.run_hook(self.fw(), rows=[call("Bash", command=cmd)]))

    def test_only_read_project_listed_not_injected(self):
        ho = self.write("other/docs/HANDOFF.md", HANDOFF)
        code = self.write("other/src/a.py")
        ctx = self.run_hook(self.fw(), rows=[call("Read", file_path=str(code)),
                                            call("Bash", command=f"ls {self.root / 'other' / 'src'}")])
        self.assertNotIn("AI 也要能同时收发", ctx)
        self.assertIn(str(ho), ctx)
        self.assertIn("只有当前任务属于它们时才去读", ctx)

    def test_projects_ordered_by_recency_and_capped(self):
        rows = []
        for name in ("p1", "p2", "p3", "p4"):
            self.write(f"{name}/docs/HANDOFF.md", f"**已谈定**：\n- {name} 的约定\n")
            rows.append(call("Write", file_path=str(self.write(f"{name}/a.py"))))
        ctx = self.run_hook(self.fw(), rows=rows)
        self.assertIn("涉及几个项目", ctx)
        self.assertLess(ctx.index("p4 的约定"), ctx.index("p3 的约定"))
        self.assertLess(ctx.index("p3 的约定"), ctx.index("p2 的约定"))
        self.assertNotIn("p1 的约定", ctx)
        self.assertIn(str(self.root / "p1/docs/HANDOFF.md"), ctx)

    def test_recency_counts_any_touch_after_strong_evidence(self):
        # 写过 A，又去写 B/C/D，最后回来读 A 的代码：A 应排第一，不被挤出前 3
        rows = []
        for name in ("pa", "pb", "pc", "pd"):
            self.write(f"{name}/docs/HANDOFF.md", f"**已谈定**：\n- {name} 的约定\n")
            rows.append(call("Write", file_path=str(self.write(f"{name}/a.py"))))
        rows.append(call("Read", file_path=str(self.root / "pa/a.py")))
        ctx = self.run_hook(self.fw(), rows=rows)
        self.assertIn("pa 的约定", ctx)
        self.assertLess(ctx.index("pa 的约定"), ctx.index("pd 的约定"))
        self.assertNotIn("pb 的约定", ctx)

    def test_handoff_only_named_in_shell_is_listed(self):
        ho = self.write("ref/docs/HANDOFF.md", HANDOFF)
        ctx = self.run_hook(self.fw(), rows=[call("Bash", command=f"echo {ho}")])
        self.assertNotIn("AI 也要能同时收发", ctx)
        self.assertIn(str(ho), ctx)

    def test_cwd_project_and_written_project_deduped(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        code = self.write("proj/src/a.py")
        ctx = self.run_hook(self.root / "proj", rows=[call("Write", file_path=str(code))])
        self.assertEqual(ctx.count("AI 也要能同时收发"), 1)
        self.assertNotIn("涉及几个项目", ctx)

    def test_deleted_outside_worktree_maps_back_to_main(self):
        # 个人仓的规矩：worktree 放仓库外、合并后删掉；对话里的路径已不存在，要靠 git worktree add 找回主仓
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        (self.root / "proj/.git").mkdir(parents=True)
        rows = [call("Bash", command=f"cd {self.root / 'proj'} && git worktree add -b feat/x ../proj-wt-x HEAD"),
                call("Write", file_path=str(self.root / "proj-wt-x/src/a.py"))]
        self.assertIn("AI 也要能同时收发", self.run_hook(self.fw(), rows=rows))

    def test_python_write_in_deleted_worktree_injected_via_worktree_evidence(self):
        # python 落盘看不出写过，但本会话为 proj 开过 worktree，足以说明在做它
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        (self.root / "proj/.git").mkdir(parents=True)
        wt = self.root / "proj-wt-x"
        rows = [call("Bash", command=f"cd {self.root / 'proj'} && git worktree add -b x ../proj-wt-x"),
                call("Bash", command=f"py -3 -c \"open(r'{wt / 'a.py'}','w')\"")]
        self.assertIn("AI 也要能同时收发", self.run_hook(self.fw(), rows=rows))

    def test_failed_worktree_add_is_no_evidence(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        (self.root / "proj/.git").mkdir(parents=True)
        rows = [call("Bash", ok=False, command=f"cd {self.root / 'proj'} && git worktree add -b x ../proj-wt-x")]
        ctx = self.run_hook(self.fw(), rows=rows)
        self.assertNotIn("AI 也要能同时收发", ctx)
        self.assertIn("只有当前任务属于它们时才去读", ctx)

    def test_missing_transcript_falls_back_to_cwd(self):
        self.write("proj/docs/HANDOFF.md", HANDOFF)
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        payload = {"source": "compact", "cwd": str(self.root / "proj"), "transcript_path": str(self.root / "nope.jsonl")}
        proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload, ensure_ascii=False),
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("AI 也要能同时收发", proc.stdout)

    def test_bad_input_passes_with_error(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        proc = subprocess.run([sys.executable, str(HOOK)], input=b"{", capture_output=True, env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("内部错误", proc.stderr.decode("utf-8"))

    def test_missing_cwd_passes(self):
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"source": "compact"}),
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
