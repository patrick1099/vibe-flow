"""hooks/doc_gate.py 的端到端测试：造假项目 + 假对话记录，跑真实脚本看输出。

运行：py -3 -m unittest discover -s tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "hooks" / "doc_gate.py"


def human(text="改一下"):
    return {"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": text}}


_ids = iter(range(10**6))


def edit(path, tool="Edit", ok=True):
    """一次写文件调用 + 它的结果，返回两行记录。"""
    tid = f"toolu_{next(_ids)}"
    call = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": tool, "input": {"file_path": str(path)}}]}}
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": not ok,
         "content": "ok" if ok else "<tool_use_error>String to replace not found</tool_use_error>"}]}}
    return [call, result]


def flatten(rows):
    out = []
    for r in rows:
        out.extend(r if isinstance(r, list) else [r])
    return out


class DocGateTest(unittest.TestCase):
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

    def run_gate(self, rows, active=False):
        tr = self.root / "transcript.jsonl"
        tr.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in flatten(rows)), encoding="utf-8")
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        proc = subprocess.run(
            [sys.executable, str(GATE)],
            input=json.dumps({"transcript_path": str(tr), "stop_hook_active": active}),
            capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def toolkit(self, with_docs):
        self.write("tk/cli.py", "# 结构: vibe-scripts/toolkit\n")
        core = self.write("tk/core.py", "def f(): pass\n")
        if with_docs:
            self.write("tk/docs/BLUEPRINT.md", "# bp")
            self.write("tk/docs/CHANGELOG.md", "# cl")
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
        self.assertIn("都没动", out["reason"])

    def test_changelog_touched_passes(self):
        core = self.toolkit(with_docs=True)
        cl = self.root / "tk/docs/CHANGELOG.md"
        self.assertIsNone(self.run_gate([human(), edit(core), edit(cl)]))

    def test_failed_changelog_edit_does_not_count(self):
        core = self.toolkit(with_docs=True)
        cl = self.root / "tk/docs/CHANGELOG.md"
        out = self.run_gate([human(), edit(core), edit(cl, ok=False)])
        self.assertIn("都没动", out["reason"])

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
        self.write("fw/docs/CHANGELOG.md", "# 公司仓自己的 changelog")
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
        self.write("shared/tool.BLUEPRINT.md")
        self.write("shared/tool.CHANGELOG.md")
        out = self.run_gate([human(), edit(s)])
        self.assertIn("都没动", out["reason"])
        self.assertNotIn("缺", out["reason"])

    def test_agents_md_marks_own_dir_even_with_test_file(self):
        s = self.write("proj/tool.py", "# 结构: vibe-scripts/standard\n")
        self.write("proj/test_tool.py", "")
        self.write("proj/AGENTS.md", "# proj")
        out = self.run_gate([human(), edit(s)])
        self.assertIn("docs", out["reason"])
        self.assertNotIn("tool.BLUEPRINT.md", out["reason"])
        self.write("proj/docs/BLUEPRINT.md")
        cl = self.write("proj/docs/CHANGELOG.md")
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
        self.write("scripts/tool.BLUEPRINT.md")
        self.write("scripts/tool.CHANGELOG.md")
        cl = self.root / "scripts/tool.CHANGELOG.md"
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
        self.assertIn("都没动", out["reason"])

    def test_bad_transcript_path_passes(self):
        env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        proc = subprocess.run([sys.executable, str(GATE)],
                              input=json.dumps({"transcript_path": str(self.root / "nope.jsonl")}),
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
