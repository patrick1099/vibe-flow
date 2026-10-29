"""skills/vibe-flow/scripts/dep_graph.py 的测试：临时项目 + 真脚本进程。"""
import json
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

    def test_default_depth_ignores_top_level_entry_module(self):
        self.write("main.py", "from app.core import x\n")
        self.write("app/__init__.py", "")
        self.write("app/core.py", "x = 1\n")
        self.write("app/store.py", "import app.core\n")
        proc = self.run_graph()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.edges(proc.stdout), {("main", "app.core"), ("app.store", "app.core")})

    def test_default_depth_collapses_two_top_level_packages(self):
        self.write("a/x.py", "import b.y\n")
        self.write("b/y.py", "")
        proc = self.run_graph()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.edges(proc.stdout), {("a", "b")})

    def test_default_depth_keeps_top_level_file_nodes(self):
        self.write("main.py", "import core\n")
        self.write("core.py", "")
        self.write("store.py", "")
        out = self.root / "g.d2"
        proc = self.run_graph("--d2", str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.edges(proc.stdout), {("main", "core")})
        nodes = {line[1:-1] for line in out.read_text(encoding="utf-8").splitlines()
                 if line.startswith('"') and line.endswith('"') and line.count('"') == 2}
        self.assertEqual(nodes, {"main", "core", "store"})

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


class SnapshotTest(DepGraphCase):
    def setUp(self):
        super().setUp()
        self.write("x.py", "from y import first\n\ndef f():\n    return 1\n")
        self.write("y.py", "first = 1\nsecond = 2\n")
        self.write("z.py", "")
        self.snapshot = self.root / "snapshots" / "依赖.json"

    def save_snapshot(self, *args):
        proc = self.run_graph("--write-snapshot", str(self.snapshot), *args)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def test_round_trip_deterministic_bytes_and_unchanged_mtime(self):
        proc = self.save_snapshot()
        self.assertTrue(proc.stdout.startswith("语言 python  模块 3  边 1  环 0\n"))
        self.assertTrue(proc.stdout.endswith(f"已写快照 {self.snapshot}\n"))
        first = self.snapshot.read_bytes()
        self.assertEqual(first, (json.dumps({
            "version": 1, "language": "python", "depth": None,
            "nodes": ["x", "y", "z"], "edges": [["x", "y"]],
        }, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        os.utime(self.snapshot, ns=(1_600_000_000_000_000_000,) * 2)
        mtime = self.snapshot.stat().st_mtime_ns
        proc = self.save_snapshot()
        self.assertEqual(self.snapshot.read_bytes(), first)
        self.assertEqual(self.snapshot.stat().st_mtime_ns, mtime)
        self.assertTrue(proc.stdout.endswith(f"快照未变 {self.snapshot}\n"))
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"与快照一致 {self.snapshot}：模块 3  边 1\n")

    def test_default_path_is_under_project_root(self):
        proc = self.run_graph("--write-snapshot")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        path = self.root / "docs/model/build.deps.json"
        self.assertTrue(path.is_file())
        self.assertTrue(proc.stdout.endswith(f"已写快照 {path}\n"))
        proc = self.run_graph("--check-snapshot")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"与快照一致 {path}：模块 3  边 1\n")

    def test_explicit_relative_path_is_resolved_from_cwd(self):
        caller = self.root / "caller"
        caller.mkdir()
        for mode in ("--write-snapshot", "--check-snapshot"):
            proc = subprocess.run([sys.executable, str(SCRIPT), str(self.root), mode, "local.json"],
                                  cwd=caller, capture_output=True, text=True, encoding="utf-8", env=ENV)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(str(caller / "local.json"), proc.stdout)
        self.assertTrue((caller / "local.json").is_file())
        self.assertFalse((self.root / "local.json").exists())

    def test_source_and_snapshot_timestamps_do_not_matter(self):
        self.save_snapshot()
        for path in (self.root / "x.py", self.snapshot):
            before = path.stat().st_mtime_ns
            os.utime(path, ns=(before - 10_000_000_000,) * 2)
            self.assertNotEqual(path.stat().st_mtime_ns, before)
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_function_body_change_does_not_matter(self):
        self.save_snapshot()
        self.write("x.py", "from y import first\n\ndef f():\n    return first + 42\n")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_another_imported_name_on_same_edge_does_not_matter(self):
        self.save_snapshot()
        self.write("x.py", "from y import first, second\n")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_added_edge_is_reported(self):
        self.save_snapshot()
        self.write("z.py", "import x\n")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, f"与快照 {self.snapshot} 不一致：模块 +0 -0  边 +1 -0\n  + 边 z -> x\n")

    def test_removed_module_and_its_edge_are_reported(self):
        self.save_snapshot()
        (self.root / "y.py").unlink()
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, f"与快照 {self.snapshot} 不一致：模块 +0 -1  边 +0 -1\n  - 模块 y\n  - 边 x -> y\n")

    def test_diff_categories_and_members_are_sorted(self):
        self.write("z.py", "import y\n")
        self.save_snapshot()
        (self.root / "y.py").unlink()
        (self.root / "z.py").unlink()
        self.write("x.py", "import b\nimport a\n")
        self.write("b.py", "")
        self.write("a.py", "")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [
            f"与快照 {self.snapshot} 不一致：模块 +2 -2  边 +2 -2",
            "  + 模块 a", "  + 模块 b", "  - 模块 y", "  - 模块 z",
            "  + 边 x -> a", "  + 边 x -> b", "  - 边 x -> y", "  - 边 z -> y",
        ])

    def test_language_change_is_reported_even_with_same_graph(self):
        self.save_snapshot()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        data["language"] = "rust"
        self.snapshot.write_text(json.dumps(data), encoding="utf-8")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, f"与快照 {self.snapshot} 不一致：模块 +0 -0  边 +0 -0\n  语言 rust → python\n")

    def test_missing_snapshot_is_usage_error_with_recovery_hint(self):
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--write-snapshot", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_snapshot_modes_and_against_are_mutually_exclusive(self):
        for args in (("--check-snapshot", "--against", "HEAD"),
                     ("--write-snapshot", "--against", "HEAD"),
                     ("--write-snapshot", "--check-snapshot")):
            with self.subTest(args=args):
                proc = self.run_graph(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertFalse(self.snapshot.exists())
        self.assertFalse((self.root / "docs/model/build.deps.json").exists())

    def test_invalid_json_version_missing_fields_and_field_types_are_usage_errors(self):
        self.save_snapshot()
        valid = json.loads(self.snapshot.read_text(encoding="utf-8"))
        cases = ["{bad json", "[]", "null"]
        cases += [json.dumps({**valid, "version": v}) for v in (2, True, "1")]
        cases += [json.dumps({k: v for k, v in valid.items() if k != field}) for field in valid]
        cases += [json.dumps({**valid, field: value}) for field, value in (
            ("language", None), ("depth", "3"), ("depth", True),
            ("nodes", "x"), ("nodes", [None]), ("edges", {}),
            ("edges", [["x"]]), ("edges", [["x", []]]),
        )]
        for content in cases:
            with self.subTest(content=content):
                self.snapshot.write_text(content, encoding="utf-8")
                proc = self.run_graph("--check-snapshot", str(self.snapshot))
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertEqual(proc.stdout, "")
                self.assertTrue(proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
        self.snapshot.write_bytes(b"\xff")
        self.assertEqual(self.run_graph("--check-snapshot", str(self.snapshot)).returncode, 2)

    def test_stored_depth_is_used_when_flag_is_omitted(self):
        self.write("pkg/ui/a.py", "from pkg.ui import b\n")
        self.write("pkg/ui/b.py", "")
        self.save_snapshot("--depth", "3")
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        self.assertEqual(data["depth"], 3)
        self.assertIn(["pkg.ui.a", "pkg.ui.b"], data["edges"])
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self.run_graph("--check-snapshot", str(self.snapshot), "--depth", "1")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("- 边 pkg.ui.a -> pkg.ui.b", proc.stdout)

    def test_explicit_depth_overrides_stored_depth_without_comparing_metadata(self):
        self.save_snapshot("--depth", "3")
        proc = self.run_graph("--check-snapshot", str(self.snapshot), "--depth", "1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_snapshot_order_and_duplicate_entries_do_not_matter(self):
        self.save_snapshot()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        data["nodes"] = ["z", "y", "x", "x"]
        data["edges"] *= 2
        self.snapshot.write_text(json.dumps(data), encoding="utf-8")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_parse_failure_and_missing_sources_are_usage_errors(self):
        self.save_snapshot()
        self.write("x.py", "def (\n")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("解析失败", proc.stderr)
        for path in self.root.glob("*.py"):
            path.unlink()
        self.assertEqual(self.run_graph("--check-snapshot", str(self.snapshot)).returncode, 2)
        self.assertEqual(self.run_graph("--write-snapshot", str(self.snapshot)).returncode, 2)

    def test_rust_snapshot_round_trip_and_added_edge(self):
        self.write("Cargo.toml", '[package]\nname = "demo"\nversion = "0.1.0"\n')
        self.write("src/lib.rs", "pub mod a;\npub mod b;\n")
        self.write("src/a.rs", "pub fn f() { crate::b::g(); }\n")
        self.write("src/b.rs", "pub fn g() {}\n")
        self.save_snapshot()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        self.assertEqual(data["language"], "rust")
        self.assertEqual(data["edges"], [["a", "b"]])
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.write("src/b.rs", "pub fn g() { crate::a::f(); }\n")
        proc = self.run_graph("--check-snapshot", str(self.snapshot))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("  + 边 b -> a\n", proc.stdout)
        self.assertNotIn("环", proc.stdout)


if __name__ == "__main__":
    unittest.main()
