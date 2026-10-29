"""model_page.py 的测试：临时项目 + 真脚本进程。"""
import html
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "clarify-needs" / "scripts" / "model_page.py"
GRAPH = ROOT / "skills" / "vibe-flow" / "scripts" / "dep_graph.py"
ENV = {**os.environ, "PYTHONUTF8": "1"}
SPEC = importlib.util.spec_from_file_location("model_page", SCRIPT)
MODEL_PAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL_PAGE)


class ModelPageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="model page 测试-")
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.write("pkg/a.py", "from pkg import b\n")
        self.write("pkg/b.py", "")
        self.source = self.write("docs/model/build.html", '<div class="layer">模块</div>')
        self.snapshot = self.root / "docs/model/build.deps.json"

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_graph(self, *args):
        return subprocess.run([sys.executable, str(GRAPH), str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", env=ENV)

    def save_snapshot(self):
        proc = self.run_graph("--write-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def render(self, source=None, *args):
        source = source or self.source
        proc = subprocess.run([sys.executable, str(SCRIPT), str(source),
                               "--title", "搭建图", *args],
                              capture_output=True, text=True, encoding="utf-8", env=ENV)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return Path(proc.stdout.strip()).read_text(encoding="utf-8")

    def test_matching_snapshot(self):
        self.save_snapshot()
        page = self.render()
        self.assertIn("已对照代码依赖", page)
        self.assertIn("模块 2 · 边 1", page)
        self.assertIn('class="comparison comparison-ok"', page)
        self.assertLess(page.index('<p class="sub">'), page.index('<div class="comparison'))
        self.assertLess(page.index('<div class="comparison'), page.index('<div class="card">'))

    def test_two_unconfirmed_differences(self):
        self.save_snapshot()
        self.write("pkg/c.py", "")
        self.write("pkg/a.py", "from pkg import b, c\n")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        differences = proc.stdout.splitlines()[1:]
        self.assertEqual(differences, ["  + 模块 pkg.c", "  + 边 pkg.a -> pkg.c"])
        page = self.render()
        self.assertIn("2 处未确认", page)
        self.assertIn('class="comparison comparison-pending"', page)
        self.assertIn("<details>", page)
        self.assertIn("<pre>" + html.escape("\n".join(differences)) + "</pre>", page)

    def test_missing_snapshot(self):
        page = self.render()
        self.assertIn("未对照", page)
        self.assertIn("还没有模块依赖快照", page)
        self.assertIn('class="comparison comparison-unchecked"', page)

    def test_other_sources_have_no_marker_and_do_not_run_graph(self):
        for rel in ("docs/model/run.html", "elsewhere/build.html", "docs/model/build.htm"):
            with self.subTest(source=rel):
                source = self.write(rel, '<div class="layer">其他图</div>')
                with patch.object(MODEL_PAGE.subprocess, "run") as run:
                    self.assertEqual(MODEL_PAGE.comparison_marker(source), "")
                run.assert_not_called()
                page = self.render(source)
                for text in ("已对照代码依赖", "处未确认", "未对照", "comparison"):
                    self.assertNotIn(text, page)

    def test_broken_snapshot_does_not_fail_rendering(self):
        self.snapshot.write_text("{}", encoding="utf-8")
        page = self.render()
        self.assertIn("未对照", page)
        self.assertIn("dep_graph: 快照缺字段", page)

    def test_code_parse_failure_does_not_fail_rendering(self):
        self.save_snapshot()
        self.write("pkg/a.py", "def broken(\n")
        page = self.render()
        self.assertIn("未对照", page)
        self.assertIn("pkg/a.py 解析失败", page)

    def test_language_and_removed_differences_are_counted_and_escaped(self):
        self.save_snapshot()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        data["language"] = "rust"
        data["nodes"].append("<old&module>")
        self.snapshot.write_text(json.dumps(data), encoding="utf-8")
        page = self.render()
        self.assertIn("2 处未确认", page)
        self.assertIn("  语言 rust → python", page)
        self.assertIn("  - 模块 &lt;old&amp;module&gt;", page)
        self.assertNotIn("  - 模块 <old&module>", page)

    def test_subprocess_failures_degrade_to_unchecked(self):
        failures = (subprocess.TimeoutExpired("dep_graph", 30),
                    FileNotFoundError("dep_graph.py 不存在"),
                    RuntimeError("<unexpected>"))
        for failure in failures:
            with self.subTest(failure=failure):
                with patch.object(MODEL_PAGE.subprocess, "run", side_effect=failure) as run:
                    marker = MODEL_PAGE.comparison_marker(self.source)
                self.assertIn("未对照", marker)
                self.assertIn("对照超时" if isinstance(failure, subprocess.TimeoutExpired)
                              else html.escape(str(failure)), marker)
                self.assertEqual(run.call_args.kwargs["timeout"], 30)
                self.assertEqual(run.call_args.args[0], [
                    sys.executable, str(GRAPH), str(self.root), "--check-snapshot",
                    str(self.snapshot)])

    def test_error_reason_uses_first_line_truncated_and_escaped(self):
        reason = "<错误>" + "长" * 140
        result = subprocess.CompletedProcess([], 2, "", reason + "\n第二行不能出现")
        with patch.object(MODEL_PAGE.subprocess, "run", return_value=result):
            marker = MODEL_PAGE.comparison_marker(self.source)
        self.assertIn(html.escape(reason[:120]), marker)
        self.assertNotIn(html.escape(reason[:121]), marker)
        self.assertNotIn("第二行不能出现", marker)

    def test_questions_and_fragment_validation_still_work(self):
        page = self.render(None, "--q", "模块::怎么分？", "--anchor", "看搭建方式")
        self.assertIn("图上这 1 处要你定", page)
        self.assertIn("怎么分？", page)
        self.assertIn("看搭建方式", page)
        self.source.write_text("<script>alert(1)</script>", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), str(self.source),
                               "--title", "搭建图"],
                              capture_output=True, text=True, encoding="utf-8", env=ENV)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("应是只含结构的 HTML 片段", proc.stderr)

    @unittest.skipUnless(shutil.which("d2"), "本机没有 d2")
    def test_d2_build_page_has_marker(self):
        self.save_snapshot()
        source = self.write("docs/model/build.d2", "a -> b\n")
        page = self.render(source)
        self.assertIn("已对照代码依赖", page)
        self.assertIn("模块 2 · 边 1", page)
        self.assertIn("data:image/svg+xml;base64,", page)


if __name__ == "__main__":
    unittest.main()
