"""skills/vibe-flow/scripts/dep_graph.py 的测试：临时项目 + 真脚本进程。"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "vibe-flow" / "scripts" / "dep_graph.py"
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
ENV = {**os.environ, "PYTHONUTF8": "1"}


class DepGraphCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="dep graph 测试-")
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run_graph(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", env=ENV)

    def edges(self, out):
        return {tuple(line.split(":")[0].strip().split(" -> ")) for line in out.splitlines() if " -> " in line and not line.lstrip().startswith(("+", "-"))}


class RustTest(DepGraphCase):
    def crate(self):
        self.write("Cargo.toml", '[package]\nname = "demo-app"\nversion = "0.1.0"\n')
        self.write("src/lib.rs", "pub mod a;\npub mod b;\npub mod c;\npub mod d;\n")

    def test_body_calls_braces_and_super_count_but_comments_strings_tests_do_not(self):
        self.crate()
        self.write("src/a.rs", 'use crate::{b::{X, Y}, c};\nfn f() { let s = "crate::d::fake"; }\n// crate::d::commented\n')
        self.write("src/b.rs", "pub struct X; pub struct Y;\nfn g() { super::c::run(); }\n")
        self.write("src/c.rs", "pub fn run() { let q = '\"'; }\n#[cfg(test)]\nmod tests { use crate::d::Thing; }\n")
        self.write("src/d.rs", "pub struct Thing;\n")
        self.write("src/main.rs", "use demo_app::a;\nfn main() {}\n")
        proc = self.run_graph()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.edges(proc.stdout), {("a", "b"), ("a", "c"), ("b", "c"), ("main", "a")})
        self.assertIn("环 0", proc.stdout)

    def test_cycle_through_function_body_call_and_path_module_owner(self):
        self.crate()
        self.write("src/a.rs", "pub fn old() { crate::b::new_impl(); }\n")
        self.write("src/b.rs", "pub fn new_impl() {}\nfn h() { crate::a::old(); }\n")
        self.write("src/c.rs", '#[path = "c_extra.rs"]\nmod extra;\n')
        self.write("src/c_extra.rs", "fn k() { crate::d::Thing; }\n")
        self.write("src/d.rs", "pub struct Thing;\n")
        proc = self.run_graph()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("环 {a, b}", proc.stdout)
        self.assertIn(("c", "d"), self.edges(proc.stdout))
        self.assertNotIn("c_extra", proc.stdout)

    def test_workspace_without_package_is_usage_error(self):
        self.write("Cargo.toml", '[workspace]\nmembers = ["x"]\n')
        self.assertEqual(self.run_graph().returncode, 2)


class PythonTest(DepGraphCase):
    def test_relative_function_level_and_submodule_imports_with_tests_excluded(self):
        self.write("app/__init__.py", "")
        self.write("app/core.py", "def rule(): pass\n")
        self.write("app/ui/__init__.py", "")
        self.write("app/ui/view.py", "from ..core import rule\n\ndef late():\n    from app import store\n")
        self.write("app/store.py", "import json\nfrom app.core import rule\n")
        self.write("tests/test_store.py", "from app.ui import view\n")
        proc = self.run_graph()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.edges(proc.stdout), {("app.ui", "app.core"), ("app.ui", "app.store"), ("app.store", "app.core")})

    def test_depth_flag_collapses_nodes(self):
        self.write("app/__init__.py", "")
        self.write("app/ui/__init__.py", "")
        self.write("app/ui/a.py", "from app.ui import b\n")
        self.write("app/ui/b.py", "")
        self.write("app/core.py", "from app.ui import a\n")
        proc = self.run_graph("--depth", "3")
        self.assertIn(("app.ui.a", "app.ui.b"), self.edges(proc.stdout))
        self.assertEqual(self.edges(self.run_graph().stdout), {("app.core", "app.ui")})

    def test_no_sources_is_usage_error(self):
        self.write("README.md", "# none\n")
        self.assertEqual(self.run_graph().returncode, 2)


@unittest.skipUnless(shutil.which("git"), "git 不可用")
class AgainstTest(DepGraphCase):
    def commit(self):
        subprocess.run(GIT + ["add", "-A"], cwd=self.root, check=True)
        subprocess.run(GIT + ["commit", "-q", "-m", "base"], cwd=self.root, check=True)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True, check=True).stdout.strip()

    def setUp(self):
        super().setUp()
        subprocess.run(GIT + ["init", "-q"], cwd=self.root, check=True)
        self.write("pkg/__init__.py", "")
        self.write("pkg/a.py", "from pkg import b\n")
        self.write("pkg/b.py", "")
        self.write("pkg/c.py", "")
        self.base = self.commit()

    def test_new_cycle_against_base_exits_1_and_writes_d2(self):
        self.write("pkg/b.py", "def f():\n    from pkg import a\n")
        out = self.root / "g.d2"
        proc = self.run_graph("--against", self.base, "--d2", str(out))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("新环 {pkg.a, pkg.b}", proc.stdout)
        self.assertIn("+ pkg.b -> pkg.a", proc.stdout)
        self.assertIn('"pkg.b" -> "pkg.a": {style: {stroke: "#dc2626"', out.read_text(encoding="utf-8"))

    def test_new_acyclic_edge_exits_0_and_old_cycle_is_not_new(self):
        self.write("pkg/b.py", "from pkg import a\n")
        base = self.commit()
        self.write("pkg/c.py", "from pkg import a\n")
        proc = self.run_graph("--against", base)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("+ pkg.c -> pkg.a", proc.stdout)
        self.assertNotIn("新环", proc.stdout)

    def test_existing_cycle_swallowing_a_module_counts_as_new(self):
        self.write("pkg/b.py", "from pkg import c\n")
        self.write("pkg/c.py", "from pkg import a\n")
        base_cycle = self.commit()
        self.write("pkg/c.py", "")
        self.write("pkg/b.py", "from pkg import a\n")
        no_c = self.commit()
        self.write("pkg/b.py", "from pkg import c\n")
        self.write("pkg/c.py", "from pkg import a\n")
        self.assertEqual(self.run_graph("--against", no_c).returncode, 1)
        self.assertEqual(self.run_graph("--against", base_cycle).returncode, 0)

    def test_unknown_revision_is_usage_error(self):
        self.assertEqual(self.run_graph("--against", "no-such-rev").returncode, 2)


if __name__ == "__main__":
    unittest.main()
