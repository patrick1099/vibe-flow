"""Offline regression for the explicitly registered source / external-document boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from doc_bindings import BindingError, Registry


class BindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="vibe-bind-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "parent"
        self.root.mkdir()
        self.git("init", "-q")
        self.sub = Path("tools/configurator")
        self.src = self.root / self.sub
        self.src.mkdir(parents=True)
        self.docs = self.base / "Vault 空间" / "T02"
        self.docs.mkdir(parents=True)
        self.common = Path(self.git("rev-parse", "--path-format=absolute", "--git-common-dir").strip())
        self.file = self.base / "bindings.json"

    def git(self, *args):
        return subprocess.run(["git", "-c", f"core.hooksPath={self.base / 'no-hook-fixture'}", *args],
                              cwd=self.root, check=True, capture_output=True,
                              text=True, encoding="utf-8").stdout

    def row(self, sub=None, docs=None):
        return {"git_common_dir": str(self.common), "source": sub or self.sub.as_posix(),
                "documents": str(docs or self.docs)}

    def load_rows(self, *rows):
        self.file.write_text(json.dumps({"version": 1, "bindings": list(rows)}, ensure_ascii=False),
                             encoding="utf-8")
        return Registry.load(self.file)

    def test_absent_config_never_probes_git(self):
        with patch.dict(os.environ, VIBE_FLOW_DOC_BINDINGS=str(self.file)), patch("subprocess.run", side_effect=AssertionError):
            reg = Registry.load()
            self.assertIsNone(reg.for_code(self.src / "main.py"))
            self.assertEqual(reg.for_closeout(self.root), [])

    def test_linked_worktree_same_repo_real_scope_and_cached_identity(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--no-gpg-sign", "-q", "--allow-empty", "-m", "fixture")
        b = self.base / "B"
        self.git("worktree", "add", "--detach", "-q", str(b), "HEAD")
        (b / self.sub).mkdir(parents=True)
        reg = self.load_rows(self.row())
        for top in (self.root, b):
            scope = top / self.sub
            expect = (scope, self.docs / "BLUEPRINT.md", self.docs / "CHANGELOG.md", "external")
            self.assertEqual(reg.for_code(scope / "removed.py"), expect)
            self.assertEqual(reg.for_closeout(top), [expect])
            self.assertEqual(reg.resolve_source(scope, expect[1]), expect)
            with patch("subprocess.run", side_effect=AssertionError("must cache per-worktree")):
                self.assertEqual(reg.for_code(scope / "other.py"), expect)
            self.assertIsNone(reg.for_code(top / "tools/configurator2/mod.py"))
            self.assertEqual(reg.for_closeout(top / "Code"), [])

    def test_closeout_explicit_handoff_overrides_cwd_and_no_fallback_for_other_handoff(self):
        docs2 = self.base / "vault2"
        docs2.mkdir()
        second = self.root / "tools/monitor"
        second.mkdir()
        reg = self.load_rows(self.row(), self.row("tools/monitor", docs2))
        self.assertEqual(reg.for_closeout(self.root), [])
        self.assertEqual(reg.for_closeout(self.src)[0][1].parent, self.docs)
        self.assertEqual(reg.for_closeout(self.src, [docs2 / "HANDOFF.md"])[0][0], second)
        self.assertEqual(reg.for_closeout(docs2)[0][1].parent, docs2)
        self.assertEqual(reg.for_closeout(None, [docs2 / "HANDOFF.md"])[0][0], second)
        self.assertEqual(reg.for_closeout(self.root, [docs2])[0][0], second)
        self.assertEqual(reg.for_closeout(self.src, [self.base / "wrong" / "HANDOFF.md"]), [])
        reg_one = self.load_rows(self.row())
        self.assertEqual(reg_one.for_closeout(self.root, [self.base / "wrong" / "HANDOFF.md"]), [])

    def test_deepest_match_and_only_one_existing_registered_scope_at_repo_root(self):
        inner = self.src / "sub"
        inner.mkdir()
        reg = self.load_rows(self.row(), self.row("tools/configurator/sub", self.base / "subdocs"),
                             self.row("missing", self.base / "otherdocs"))
        self.assertEqual(reg.for_code(inner / "main.py")[0], inner)
        self.assertEqual(reg.for_code(self.src / "main.py")[0], self.src)
        self.assertEqual(reg.for_closeout(self.root), [])
        inner.rmdir()
        self.assertEqual(reg.for_closeout(self.root)[0][0], self.src)
        with self.assertRaises(BindingError):
            reg.resolve_source(self.root, self.docs / "BLUEPRINT.md")
        with self.assertRaises(BindingError):
            reg.resolve_source(self.src, self.base / "wrong" / "BLUEPRINT.md")

    def test_invalid_registry_does_not_expand_to_whole_repo(self):
        for sub in (".", "..", "tools/../Code", "tools/./configurator", "/outside", "C:/outside", ".git/x", ""):
            with self.subTest(source=sub), self.assertRaises(BindingError):
                self.load_rows({**self.row(), "source": sub})
        with self.assertRaises(BindingError):
            self.load_rows({**self.row(), "documents": "elsewhere"})
        with self.assertRaises(BindingError):
            self.load_rows(self.row(), self.row(docs=self.base / "ambiguous"))
        for bad in ("{", "null", '{"version":2,"bindings":[]}', '{"version":true,"bindings":{}}'):
            with self.subTest(bad=bad), self.assertRaises(BindingError):
                self.file.write_text(bad, encoding="utf-8")
                Registry.load(self.file)

    def test_registration_resolve_failure_is_a_binding_error(self):
        self.load_rows(self.row())
        original = Path.resolve
        def resolve(p, *args, **kwargs):
            if p == self.docs:
                raise RuntimeError("symlink loop")
            return original(p, *args, **kwargs)
        with patch.object(Path, "resolve", resolve), self.assertRaises(BindingError):
            Registry.load(self.file)

    def test_nested_foreign_repo_is_not_a_registered_source(self):
        self.git("init", "-q", str(self.src))
        reg = self.load_rows(self.row())
        self.assertIsNone(reg.for_code(self.src / "file.py"))
        self.assertEqual(reg.for_closeout(self.root), [])

    def make_link(self, link, target):
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)

    def test_symlink_cannot_expand_registered_scope(self):
        outside = self.base / "other-code"
        outside.mkdir()
        link = self.src / "jump"
        self.make_link(link, outside)
        reg = self.load_rows(self.row())
        self.assertIsNone(reg.for_code(link / "main.py"))
        with self.assertRaises(BindingError):
            reg.resolve_source(link, self.docs / "BLUEPRINT.md")
        root_alias = self.root / "badprefix"
        self.make_link(root_alias, self.root)
        wrong = self.load_rows(self.row("badprefix", self.base / "bad"))
        self.assertIsNone(wrong.for_code(self.root / "Code" / "other.c"))
        self.assertEqual(wrong.for_closeout(self.root), [])


if __name__ == "__main__":
    unittest.main()
