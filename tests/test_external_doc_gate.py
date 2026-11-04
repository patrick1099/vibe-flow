"""External doc pairs: regression tests against the real gate and receipt API."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
import doc_gate


class ExternalGateTest(unittest.TestCase):
    def setUp(self):
        parent = self.enter_temp()
        self.repo = parent / "company"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.source = self.repo / "tools" / "configurator"
        self.source.mkdir(parents=True)
        self.code = self.source / "cli.py"
        self.code.write_text("pass\n", encoding="utf-8")
        self.docs = parent / "vault" / "T02"
        self.docs.mkdir(parents=True)
        self.bp = self.docs / "BLUEPRINT.md"
        self.cl = self.docs / "CHANGELOG.md"
        cfg = parent / "bindings.json"
        cfg.write_text(json.dumps({"version": 1, "bindings": [{"git_common_dir": str(self.repo / ".git"), "source": "tools/configurator", "documents": str(self.docs)}]}), encoding="utf-8")
        env = patch.dict(os.environ, {"VIBE_FLOW_DOC_BINDINGS": str(cfg), "VIBE_FLOW_RECEIPTS": str(parent / "receipts")})
        env.start()
        self.addCleanup(env.stop)

    def enter_temp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_changed_code_requires_both_external_files(self):
        issues = doc_gate.evaluate([self.code])
        self.assertEqual([(kind, proj["bp"], missing) for kind, proj, missing in issues],
                         [("missing", self.bp, ["BLUEPRINT.md", "CHANGELOG.md"])])
        self.bp.touch()
        self.assertEqual(doc_gate.evaluate([self.code])[0][2], ["CHANGELOG.md"])

    def test_handoff_write_checks_presence_but_does_not_age_docs(self):
        handoff = self.docs / "HANDOFF.md"
        handoff.touch()
        self.assertEqual(len(doc_gate.evaluate([handoff])), 1)
        self.bp.touch(); self.cl.touch()
        for p in (self.bp, self.cl):
            os.utime(p, (100, 100))
        self.assertEqual(doc_gate.evaluate([handoff]), [])
        self.assertEqual(doc_gate.evaluate([], closeout_cwd=self.repo), [])
        self.cl.unlink()
        self.assertEqual(doc_gate.evaluate([], closeout_cwd=self.repo)[0][2], ["CHANGELOG.md"])
        self.assertEqual(doc_gate.evaluate([self.docs / "notes.md"]), [])

    def test_unreadable_or_wrong_shape_receipt_cannot_disable_gate(self):
        import receipt
        self.bp.touch(); self.cl.touch()
        for f in (self.bp, self.cl):
            os.utime(f, (100, 100))
        path = receipt._store_file(self.bp, self.cl, self.source)
        path.parent.mkdir(parents=True)
        path.write_text("[]", encoding="utf-8")
        self.assertEqual(doc_gate.evaluate([self.code])[0][0], "stale")

    def test_external_receipt_refuses_tracked_file_redirected_outside_source(self):
        import receipt
        package = self.source / "pkg"
        package.mkdir()
        tracked = package / "mod.py"
        tracked.write_text("pass\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "--", "tools"], check=True, capture_output=True)
        tracked.unlink()
        package.rmdir()
        external = self.repo.parent / "outside"
        external.mkdir()
        (external / "mod.py").write_text("pass\n", encoding="utf-8")
        if os.name == "nt":
            subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(package), str(external)], check=True, capture_output=True)
        else:
            package.symlink_to(external, target_is_directory=True)
        self.bp.touch(); self.cl.touch()
        with self.assertRaises(receipt.Unverifiable):
            receipt.write(self.bp, "internal", doc_gate.DOC_SUFFIXES, doc_gate.SCAN_SUFFIXES, self.source)

    def test_receipt_for_one_checkout_does_not_cover_another(self):
        cmd = ["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
               "-c", "core.hooksPath=" + str(self.repo.parent / "empty-hooks")]
        subprocess.run(cmd + ["add", "--", "tools"], check=True, capture_output=True)
        subprocess.run(cmd + ["commit", "-qm", "fixture"], check=True, capture_output=True)
        other = self.repo.parent / "another checkout"
        subprocess.run(cmd + ["worktree", "add", "-q", "--detach", str(other)], check=True, capture_output=True)
        for p in (self.bp, self.cl):
            p.touch()
            os.utime(p, (100, 100))
        args = ["--blueprint", str(self.bp), "--source", str(self.source), "--reason", "reviewed"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(doc_gate.receipt_main(args), 0)
        self.assertEqual(doc_gate.evaluate([self.code]), [])
        self.assertEqual(doc_gate.evaluate([other / "tools" / "configurator" / "cli.py"])[0][0], "stale")

    def test_internal_change_can_be_receipted_for_the_bound_worktree_only(self):
        for p in (self.bp, self.cl):
            p.write_text("baseline\n", encoding="utf-8")
            os.utime(p, (100, 100))
        issue = doc_gate.evaluate([self.code])
        self.assertEqual(issue[0][0], "stale")
        self.assertIn('--source', doc_gate.render_reason(issue))
        args = ["--blueprint", str(self.bp), "--source", str(self.source), "--reason", "internal"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(doc_gate.receipt_main(args), 0)
        self.assertEqual(doc_gate.evaluate([self.code]), [])
        self.code.write_text("print(1)\n", encoding="utf-8")
        self.assertEqual(doc_gate.evaluate([self.code])[0][0], "stale")
        self.cl.unlink()
        self.assertEqual(doc_gate.evaluate([self.code])[0][0], "missing")
