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

    def run_hook(self, cwd, source="compact"):
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        payload = {"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd)}
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
