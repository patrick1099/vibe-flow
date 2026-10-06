"""hooks/receipt.py：文档闸「这批不用记」回执的端到端测试。

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
from pathlib import Path

from test_doc_gate import GATE, STALE, edit, flatten, human, notification, set_mtime

HOOKS = GATE.parent


class ReceiptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = self.root / "receipts"
        self.long_ago = time.time() - 3600
        self.env = dict(os.environ, VIBE_FLOW_DOC_GATE_HOME=str(self.root), VIBE_FLOW_RECEIPTS=str(self.store),
                        GIT_CEILING_DIRECTORIES=str(self.root.parent))

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text=""):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def doc(self, rel, text="# doc"):
        p = self.write(rel, text)
        set_mtime(p, self.long_ago)
        return p

    def toolkit(self, with_docs=True):
        self.write("tk/cli.py", "# 结构: vibe-scripts/toolkit\n")
        core = self.write("tk/core.py", "def f(): pass\n")
        if with_docs:
            self.doc("tk/docs/BLUEPRINT.md", "# bp")
            self.doc("tk/docs/CHANGELOG.md", "# cl")
        return core

    def run_gate(self, rows):
        tr = self.root / "transcript.jsonl"
        tr.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in flatten(rows)), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(GATE)], input=json.dumps({"transcript_path": str(tr)}),
                              capture_output=True, text=True, encoding="utf-8", env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def receipt(self, bp, reason="纯内部重构，用户没感知"):
        return subprocess.run([sys.executable, str(GATE), "receipt", "--blueprint", str(bp), "--reason", reason],
                              capture_output=True, text=True, encoding="utf-8", env=self.env)

    def test_receipt_silences_same_batch_after_wakeup(self):
        # 原案例：拦下 → AI 判断不用记 → 后台任务完成把 AI 唤醒，本轮再结束一次，不该再拦
        core = self.toolkit()
        rows = [human(), edit(core)]
        out = self.run_gate(rows)
        self.assertIn(STALE, out["reason"])
        self.assertIn("receipt --blueprint", out["reason"])
        self.assertIn(str(self.root / "tk/docs/BLUEPRINT.md"), out["reason"])
        proc = self.receipt(self.root / "tk/docs/BLUEPRINT.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(self.run_gate(rows + [notification()]))

    def test_code_change_after_receipt_blocks_again(self):
        core = self.toolkit()
        self.receipt(self.root / "tk/docs/BLUEPRINT.md")
        core.write_text("def f(): return 2\n", encoding="utf-8")
        self.assertIn(STALE, self.run_gate([human(), edit(core)])["reason"])

    def test_new_or_deleted_file_after_receipt_blocks_again(self):
        core = self.toolkit()
        self.receipt(self.root / "tk/docs/BLUEPRINT.md")
        extra = self.write("tk/extra.py", "pass\n")
        self.assertIn(STALE, self.run_gate([human(), edit(core)])["reason"])
        extra.unlink()
        self.assertIsNone(self.run_gate([human(), edit(core)]))
        core.unlink()
        self.assertIn(STALE, self.run_gate([human(), edit(core)])["reason"])

    def test_old_receipt_does_not_revive_after_docs_moved_on(self):
        # A 写过回执 → 改成 B 并更新文档 → 代码退回 A：文档描述的是 B，旧回执不能重新生效
        core = self.toolkit()
        self.receipt(self.root / "tk/docs/BLUEPRINT.md")
        cl = self.root / "tk/docs/CHANGELOG.md"
        cl.write_text("# cl\n- 改成 B\n", encoding="utf-8")
        set_mtime(cl, self.long_ago)
        os.utime(core, None)
        self.assertIn(STALE, self.run_gate([human(), edit(core)])["reason"])

    def test_missing_docs_cannot_take_receipt(self):
        core = self.toolkit(with_docs=False)
        proc = self.receipt(self.root / "tk/docs/BLUEPRINT.md")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("回执没写", proc.stderr)
        self.assertIn("BLUEPRINT.md", self.run_gate([human(), edit(core)])["reason"])

    def test_receipt_requires_reason(self):
        self.toolkit()
        self.assertEqual(self.receipt(self.root / "tk/docs/BLUEPRINT.md", reason="  ").returncode, 2)

    def test_sibling_receipt_does_not_cover_neighbour_script(self):
        a = self.write("tools/a.py", "# 结构: vibe-scripts/standard\nprint(1)\n")
        b = self.write("tools/b.py", "# 结构: vibe-scripts/standard\nprint(2)\n")
        for s in ("a", "b"):
            self.doc(f"tools/{s}.BLUEPRINT.md")
            self.doc(f"tools/{s}.CHANGELOG.md")
        self.assertEqual(self.receipt(self.root / "tools/a.BLUEPRINT.md").returncode, 0)
        out = self.run_gate([human(), edit(a), edit(b)])
        self.assertIn(str(self.root / "tools/b.BLUEPRINT.md"), out["reason"])
        self.assertNotIn(str(self.root / "tools/a.BLUEPRINT.md"), out["reason"])
        # 邻居脚本改了，不影响 a 的回执
        b.write_text("# 结构: vibe-scripts/standard\nprint(3)\n", encoding="utf-8")
        self.assertIsNone(self.run_gate([human(), edit(a)]))

    def test_code_outside_snapshot_is_not_exempted(self):
        # 被 gitignore 的文件不在快照里，改了它指纹不变；回执无法证明它审过，照常提醒
        if not shutil.which("git"):
            self.skipTest("git 不可用")
        core = self.toolkit()
        self.write("tk/.gitignore", "gen.py\n")
        gen = self.write("tk/gen.py", "x = 1\n")
        git = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
        subprocess.run(git + ["init", "-q"], cwd=self.root / "tk", check=True)
        subprocess.run(git + ["add", "."], cwd=self.root / "tk", check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], cwd=self.root / "tk", check=True)
        self.assertEqual(self.receipt(self.root / "tk/docs/BLUEPRINT.md").returncode, 0)
        self.assertIsNone(self.run_gate([human(), edit(core)]))
        gen.write_text("x = 2\n", encoding="utf-8")
        self.assertIn(STALE, self.run_gate([human(), edit(gen)])["reason"])

    def test_receipt_recognized_with_any_subset_of_paths(self):
        # session-sweep 只把每目录最新的一个文件传给 evaluate；回执按整份快照认，与传入哪些路径无关
        core = self.toolkit()
        sub = self.write("tk/pkg/mod.py", "pass\n")
        self.receipt(self.root / "tk/docs/BLUEPRINT.md")
        old = dict(os.environ)
        os.environ["VIBE_FLOW_RECEIPTS"] = str(self.store)
        try:
            sys.path.insert(0, str(HOOKS))
            import doc_gate
            for paths in ([core], [sub], [core, sub, self.root / "tk/cli.py"]):
                self.assertEqual(doc_gate.evaluate([str(p) for p in paths], stop_at=str(self.root)), [])
            sub.write_text("pass  # changed\n", encoding="utf-8")
            self.assertEqual([k for k, *_ in doc_gate.evaluate([str(core)], stop_at=str(self.root))], ["stale"])
        finally:
            sys.path.remove(str(HOOKS))
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
