"""HANDOFF persistence, blocked handoffs, recovery, and actual CLI contracts."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/subagent-foreman/scripts/batch_state.py"
spec = importlib.util.spec_from_file_location("batch_state", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BatchStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="batch-state-")
        self.root = Path(self.tmp.name).resolve()
        self.handoff = self.root / "HANDOFF.md"
        self.agreed = "# HANDOFF\n\n## 已谈定\n\n- keep this agreement\n"
        self.handoff.write_text(self.agreed, encoding="utf-8")
        self.record = {"schema": 1, "workspace": str(self.root), "batch": "b1", "supervisor": "s1",
                       "baseline": "abc123; dirty: user.txt", "outcome": "active", "docs": "pending",
                       "tasks": [{"id": "t1", "state": "pending", "acceptance": "run command; expect value 42", "evidence": []}],
                       "workers": [], "next": ["start t1"]}

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, expected="missing", dry=False):
        return module.save(self.handoff, self.record, self.root, self.record["batch"], expected, dry, initialize=(expected == "missing"))

    def finish(self):
        (self.root / "result.log").write_text("command -> exit 0; value=42", encoding="utf-8")
        self.record["tasks"][0].update(state="verified", evidence=["result.log"])
        self.record.update(outcome="complete", docs="done")

    def cli(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True,
                              encoding="utf-8")

    def test_save_preserves_agreements_and_succeeding_text(self):
        revision = self.save()["revision"]
        self.handoff.write_text(self.handoff.read_text(encoding="utf-8") + "\n## Other work\nKeep it.\n", encoding="utf-8")
        _, _, current = module.read_handoff(self.handoff)
        self.assertNotEqual(current, revision)
        self.record["next"] = ["continue t1"]
        self.save(current)
        saved = self.handoff.read_text(encoding="utf-8")
        self.assertTrue(saved.startswith(self.agreed.rstrip()))
        self.assertTrue(saved.endswith("\n## Other work\nKeep it.\n"))

    def test_dry_run_uses_checks_without_writing(self):
        before = self.handoff.read_bytes()
        self.assertTrue(self.save(dry=True)["dry_run"])
        self.assertEqual(before, self.handoff.read_bytes())
        self.assertFalse(list(self.root.glob("*.lock")))
        with self.assertRaises(module.StateError):
            self.save(expected="stale", dry=True)

    def test_stale_write_is_rejected(self):
        old = self.save()["revision"]
        self.record["next"] = ["changed"]
        new = self.save(old)["revision"]
        with self.assertRaises(module.StateError):
            self.save(old)
        self.assertEqual(module.read_handoff(self.handoff)[2], new)

    def test_write_failure_preserves_previous_handoff(self):
        before = self.handoff.read_bytes()
        with patch.object(module.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.save()
        self.assertEqual(self.handoff.read_bytes(), before)
        self.assertFalse(list(self.root.glob("*.tmp")))
        self.assertFalse(list(self.root.glob("*.lock")))

    def test_existing_lock_not_removed(self):
        lock = self.root / "HANDOFF.md.batch.lock"
        lock.write_text("other writer", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.save()
        self.assertEqual(lock.read_text(encoding="utf-8"), "other writer")

    def test_corrupt_or_duplicate_markers_never_overwritten(self):
        for body in (module.START, module.END, module.START + module.END, module.START * 2 + module.END):
            with self.subTest(body=body):
                self.handoff.write_text(body, encoding="utf-8")
                with self.assertRaises(module.StateError):
                    self.save()
                self.assertEqual(self.handoff.read_text(encoding="utf-8"), body)

    def test_running_and_timeout_workers_block_ready(self):
        self.record["workers"] = [{"id": "worker-timeout-but-alive", "state": "running"}]
        self.save()
        with self.assertRaises(module.StateError):
            module.ready(self.record)
        self.record.update(outcome="blocked", docs="done")
        with self.assertRaises(module.StateError):
            module.validate(self.record, self.root, "b1")
        self.record["workers"][0]["state"] = "stopped"
        module.validate(self.record, self.root, "b1")
        module.ready(self.record)

    def test_parallel_work_rejected(self):
        self.record["workers"] = [{"id": "w1", "state": "running"}, {"id": "w2", "state": "running"}]
        with self.assertRaises(module.StateError):
            self.save()

    def test_duplicate_ids_rejected(self):
        self.record["tasks"].append(copy.deepcopy(self.record["tasks"][0]))
        with self.assertRaises(module.StateError):
            self.save()

    def test_workspace_and_batch_mismatch(self):
        for workspace, batch in ((self.root.parent, "b1"), (self.root, "other")):
            with self.assertRaises(module.StateError):
                module.validate(self.record, workspace, batch)

    def test_verified_requires_real_contained_evidence(self):
        self.record["tasks"][0]["state"] = "verified"
        for paths in ([], ["missing.log"], [str(self.handoff)], ["../outside.log"]):
            self.record["tasks"][0]["evidence"] = paths
            with self.subTest(paths=paths), self.assertRaises(module.StateError):
                self.save()

    def test_implemented_is_not_verified_after_restart(self):
        self.record["tasks"][0]["state"] = "implemented"
        self.save()
        _, recovered, _ = module.read_handoff(self.handoff)
        self.assertEqual(recovered["tasks"][0]["state"], "implemented")
        recovered.update(outcome="complete", docs="done")
        with self.assertRaises(module.StateError):
            module.validate(recovered, self.root, "b1")

    def test_next_batch_requires_previous_ready(self):
        first = self.save()["revision"]
        old = copy.deepcopy(self.record)
        self.record.update(batch="b2", supervisor="s2")
        with self.assertRaises(module.StateError):
            self.save(first)
        self.record = old
        self.finish()
        second = self.save(first)["revision"]
        self.record.update(batch="b2", supervisor="s2", outcome="active", docs="pending")
        self.save(second)
        self.assertEqual(module.read_handoff(self.handoff)[1]["supervisor"], "s2")

    def test_recorded_worker_blocks_supervisor_change(self):
        self.record["workers"] = [{"id": "w1", "state": "running"}]
        rev = self.save()["revision"]
        self.record["supervisor"] = "s2"
        self.record["workers"][0]["state"] = "stopped"
        with self.assertRaises(module.StateError):
            self.save(rev)
        # Reconcile the old batch after an external host-stop check, then replace its owner.
        self.record["supervisor"] = "s1"
        reconciled = self.save(rev)["revision"]
        self.record["supervisor"] = "s2"
        self.save(reconciled)
        self.assertEqual(module.read_handoff(self.handoff)[1]["supervisor"], "s2")

    def test_complete_and_short_status(self):
        self.finish()
        revision = self.save()["revision"]
        module.ready(self.record)
        self.record["next"] = ["x" * 10000] * 100
        output = module.summary(self.record, revision)
        self.assertNotIn("acceptance", json.dumps(output))
        self.assertLess(len(json.dumps(output)), 1600)
        self.assertFalse(output["host_lifecycle_checked"])

    def test_cli_eager_help_and_argument_errors(self):
        self.assertEqual(self.cli("--ai-help").returncode, 0)
        invalid = self.cli("--nonsense", "--json")
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, "")
        self.assertEqual(json.loads(invalid.stderr)["error"]["code"], "E_VALIDATION")
        self.assertNotEqual(self.cli("--", "--ai-help").returncode, 0)

    def test_cli_end_to_end_and_json_alias(self):
        input_file = self.root / "input.json"
        input_file.write_text(json.dumps(self.record), encoding="utf-8")
        common = ["--handoff", str(self.handoff), "--workspace", str(self.root), "--batch", "b1"]
        saved = self.cli("save", *common, "--input-file", str(input_file), "--expect", "missing", "--init", "--json")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        standard = self.cli("status", *common, "--json")
        alias = self.cli("status", *common, "--format", "json")
        self.assertEqual(standard.stdout, alias.stdout)
        self.assertEqual(set(json.loads(alias.stdout)), {"ok", "data", "error", "meta"})
        failed = self.cli("check", *common, "--ready", "--json")
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(failed.stdout, "")
        self.assertFalse(json.loads(failed.stderr)["ok"])

    def test_cli_switches_batches_using_previous_revision(self):
        self.finish()
        rev = self.save()["revision"]
        common = ["--handoff", str(self.handoff), "--workspace", str(self.root)]
        previous = self.cli("status", *common, "--batch", "b1", "--json")
        self.assertEqual(json.loads(previous.stdout)["data"]["revision"], rev)
        self.record.update(batch="b2", supervisor="s2", outcome="active", docs="pending")
        input_file = self.root / "b2.json"
        input_file.write_text(json.dumps(self.record), encoding="utf-8")
        switched = self.cli("save", *common, "--batch", "b2", "--input-file", str(input_file), "--expect", rev, "--json")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        self.assertEqual(module.read_handoff(self.handoff)[1]["batch"], "b2")

    def test_lost_record_cannot_implicitly_reinitialize(self):
        self.save()
        self.handoff.write_text(self.agreed, encoding="utf-8")
        with self.assertRaises(module.StateError):
            module.save(self.handoff, self.record, self.root, "b1", "missing")

    def test_compaction_does_not_inject_machine_progress(self):
        anchor_script = SCRIPT.parents[3] / "hooks/compact_anchor.py"
        anchor_spec = importlib.util.spec_from_file_location("batch_anchor", anchor_script)
        anchor = importlib.util.module_from_spec(anchor_spec)
        anchor_spec.loader.exec_module(anchor)
        for heading in ("# 已谈定", "## 已谈定", "**已谈定**："):
            self.handoff.write_text(heading + "\n\n- keep this agreement\n", encoding="utf-8")
            self.save()
            section = anchor.agreed_section(self.handoff)
            self.assertIn("keep this agreement", section)
            self.assertNotIn(module.START, section)
            self.assertNotIn('"supervisor"', section)

    def test_duplicate_json_and_nan_rejected(self):
        for body in ('{"schema":1,"schema":1}', '{"schema":NaN}'):
            with self.assertRaises(module.StateError):
                module.parse_json(body)


if __name__ == "__main__":
    unittest.main()
