"""Codex 事件 -> 实际 hook 进程 -> 共用判定，完全离线的 stdlib 回归测试。"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "hooks" / "doc_gate_codex.py"
SUCCESS = "Success. Updated the following files:\n"


class CodexDocGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="vibe codex 测试-")
        self.root = Path(self.tmp.name)
        self.state = self.root / "plugin-data"
        self.env = dict(os.environ, PLUGIN_DATA=str(self.state), VIBE_FLOW_DOC_GATE_HOME=str(self.root))
        self.env.pop("CLAUDE_PLUGIN_DATA", None)
        self.seq = 0

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text=""):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def project(self, name="项目", docs=True):
        self.write(name + "/cli.py", "# 结构: vibe-scripts/toolkit\n")
        core = self.write(name + "/src/core.py", "def f(): pass\n")
        if docs:
            self.write(name + "/docs/BLUEPRINT.md", "# bp")
            self.write(name + "/docs/CHANGELOG.md", "# cl")
        return core

    def event(self, kind, **fields):
        return dict(session_id="session-1", turn_id="turn-1", cwd=str(self.root),
                    hook_event_name=kind, **fields)

    def run_gate(self, data, env=None, code=0):
        proc = subprocess.run([sys.executable, str(GATE)], input=json.dumps(data, ensure_ascii=False),
                              capture_output=True, text=True, encoding="utf-8", env=env or self.env)
        self.assertEqual(proc.returncode, code, proc.stderr)
        if code:
            self.assertEqual(proc.stdout, "")
            self.assertIn("已放行", proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def patch(self, *paths, response=None, patch="", **fields):
        self.seq += 1
        data = self.event("PostToolUse", tool_name="apply_patch", tool_use_id=f"call-{self.seq}",
                          tool_input={"command": patch},
                          tool_response=response if response is not None else
                          {"stdout": SUCCESS + "".join(f"M {p}\n" for p in paths), "exit_code": 0})
        data.update(fields)
        self.assertIsNone(self.run_gate(data))
        return data

    def stop(self, **fields):
        data = self.event("Stop", stop_hook_active=False)
        data.update(fields)
        return self.run_gate(data)

    def test_missing_documents_block(self):
        self.patch(self.project(docs=False))
        out = self.stop()
        self.assertEqual(out["decision"], "block")
        self.assertIn("BLUEPRINT.md", out["reason"])

    def test_untouched_documents_block(self):
        self.patch(self.project())
        self.assertIn("都没动", self.stop()["reason"])

    def test_successful_document_write_passes(self):
        self.patch(self.project())
        self.patch(self.root / "项目/docs/CHANGELOG.md")
        self.assertIsNone(self.stop())

    def test_missing_blueprint_blocks_even_when_changelog_touched(self):
        core = self.project()
        (self.root / "项目/docs/BLUEPRINT.md").unlink()
        self.patch(core, self.root / "项目/docs/CHANGELOG.md")
        self.assertIn("缺 BLUEPRINT.md", self.stop()["reason"])

    def test_failed_patch_does_not_count(self):
        core = self.project()
        self.patch(core, response={"stdout": "patch failed", "exit_code": 1})
        self.assertIsNone(self.stop())

    def test_failed_document_patch_does_not_satisfy_gate(self):
        core = self.project()
        self.patch(core)
        self.patch(response={"output": SUCCESS + "M 项目/docs/CHANGELOG.md\n",
                             "metadata": {"exit_code": 1}})
        self.assertIn("都没动", self.stop()["reason"])

    def test_error_flags_and_absent_results_are_ignored(self):
        self.project()
        for response in [{}, {"is_error": True, "stdout": SUCCESS + "M 项目/src/core.py\n"},
                         {"isError": True, "output": SUCCESS + "M 项目/src/core.py\n"}]:
            with self.subTest(response=response):
                self.patch(response=response)
                self.assertIsNone(self.stop())

    def test_supported_success_output_shapes(self):
        self.project()
        output = SUCCESS + "M 项目/src/core.py\n"
        for response in [output, output.replace("\n", "\r\n"), {"output": output, "metadata": {"exit_code": 0}},
                         json.dumps({"output": output, "metadata": {"exit_code": 0}})]:
            with self.subTest(response=response):
                self.patch(response=response)
                self.assertEqual(self.stop()["decision"], "block")

    def test_other_tools_cannot_spoof_success(self):
        self.patch(self.project(), tool_name="Bash")
        self.assertIsNone(self.stop())

    def test_dirty_files_alone_do_not_trigger_gate(self):
        self.project()
        self.assertIsNone(self.stop())

    def test_stop_hook_active_passes_and_clears(self):
        self.patch(self.project(docs=False))
        self.assertIsNone(self.stop(stop_hook_active=True))
        self.assertIsNone(self.stop())

    def test_consumed_turn_does_not_block_twice(self):
        self.patch(self.project())
        self.assertIsNotNone(self.stop())
        self.assertIsNone(self.stop())
        self.assertEqual(list(self.state.rglob("*.json")), [])

    def test_turns_are_isolated(self):
        self.patch(self.project())
        self.assertIsNone(self.stop(turn_id="turn-2"))
        self.assertIsNotNone(self.stop())

    def test_sessions_are_isolated(self):
        self.patch(self.project())
        self.assertIsNone(self.stop(session_id="session-2"))
        self.assertIsNotNone(self.stop())

    def test_relative_paths_use_event_cwd(self):
        self.project(name="project with spaces")
        self.patch("src/core.py", cwd=str(self.root / "project with spaces"))
        self.assertIsNotNone(self.stop())

    def test_move_checks_source_project_as_well(self):
        original = self.project()
        destination = self.write("unmarked/new.py", "pass\n")
        original.unlink()
        self.patch(destination, patch=f"*** Begin Patch\n*** Update File: {original}\n"
                   f"*** Move to: {destination}\n@@\n-old\n+new\n*** End Patch")
        self.assertIn(str(original.parent.parent), self.stop()["reason"])

    def test_deleted_code_still_checks_its_project(self):
        core = self.project()
        core.unlink()
        self.patch(response={"stdout": SUCCESS + f"D {core}\n", "exit_code": 0})
        self.assertIsNotNone(self.stop())

    def test_shared_script_layout_uses_common_rule(self):
        script = self.write("mixed/tool.py", "# 结构: vibe-scripts/standard\n")
        self.patch(script)
        self.assertIn("tool.BLUEPRINT.md", self.stop()["reason"])

    def test_micro_and_unmarked_projects_are_ignored(self):
        micro = self.write("micro/tiny.py", "# 结构: vibe-scripts/micro\n")
        unmarked = self.write("work/main.c", "int main(void) {return 0;}\n")
        self.patch(micro, unmarked)
        self.assertIsNone(self.stop())

    def test_handoff_does_not_satisfy_gate(self):
        self.patch(self.project(), self.write("项目/docs/HANDOFF.md", "ongoing"))
        self.assertIn("都没动", self.stop()["reason"])

    def test_parallel_tools_keep_all_records(self):
        paths = [self.project(name=f"project-{i}") for i in range(4)]
        events = [self.event("PostToolUse", tool_name="apply_patch", tool_use_id=f"parallel-{i}",
                             tool_response={"stdout": SUCCESS + f"M {p}\n", "exit_code": 0})
                  for i, p in enumerate(paths)]
        with concurrent.futures.ThreadPoolExecutor() as pool:
            list(pool.map(self.run_gate, events))
        out = self.stop()
        for p in paths:
            self.assertIn(str(p.parent.parent), out["reason"])

    def test_repeated_call_id_is_idempotent(self):
        data = self.patch(self.project())
        self.run_gate(data)
        self.assertEqual(len(list(self.state.rglob("*.json"))), 1)
        self.assertIsNotNone(self.stop())

    def test_interrupt_cleans_only_this_turn(self):
        core = self.project()
        self.patch(core)
        self.patch(core, turn_id="turn-2")
        self.run_gate(self.event("Interrupt"))
        self.assertIsNone(self.stop())
        self.assertIsNotNone(self.stop(turn_id="turn-2"))

    def test_identifiers_cannot_escape_plugin_data(self):
        identity = {"session_id": "../../outside", "turn_id": "../other", "tool_use_id": "../../bad"}
        self.patch(self.project(), **identity)
        records = list(self.state.rglob("*.json"))
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].resolve().is_relative_to(self.state.resolve()))
        self.assertIsNotNone(self.stop(session_id=identity["session_id"], turn_id=identity["turn_id"]))

    def test_missing_plugin_data_reports_nonblocking_error(self):
        env = dict(self.env)
        env.pop("PLUGIN_DATA")
        self.run_gate(self.event("Stop"), env=env, code=1)

    def test_corrupt_state_reports_nonblocking_error(self):
        self.patch(self.project())
        next(self.state.rglob("*.json")).write_text("not JSON", encoding="utf-8")
        self.run_gate(self.event("Stop"), code=1)

    def test_bad_input_reports_nonblocking_error(self):
        proc = subprocess.run([sys.executable, str(GATE)], input="broken JSON",
                              capture_output=True, text=True, encoding="utf-8", env=self.env)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("已放行", proc.stderr)

    def test_compatibility_plugin_data_variable(self):
        self.patch(self.project())
        env = dict(self.env, CLAUDE_PLUGIN_DATA=str(self.state))
        env.pop("PLUGIN_DATA")
        self.assertIsNotNone(self.run_gate(self.event("Stop"), env=env))

    def test_plugin_uses_separate_portable_hook_file(self):
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        other = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["name"], manifest["version"]), (other["name"], other["version"]))
        hooks = json.loads((ROOT / manifest["hooks"]).read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(set(hooks), {"PostToolUse", "Stop", "Interrupt"})
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "^apply_patch$")
        for groups in hooks.values():
            handler = groups[0]["hooks"][0]
            self.assertEqual(handler["commandWindows"], 'py -3 "${PLUGIN_ROOT}/hooks/doc_gate_codex.py"')
            self.assertIn('"${PLUGIN_ROOT}/hooks/doc_gate_codex.py"', handler["command"])
        claude = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(claude["hooks"]), {"Stop"})
        self.assertIn("/hooks/doc_gate.py", claude["hooks"]["Stop"][0]["hooks"][0]["command"])

    def test_both_entries_share_the_same_evaluator(self):
        sys.path.insert(0, str(ROOT / "hooks"))
        try:
            import doc_gate
            import doc_gate_codex
            self.assertIs(doc_gate.evaluate, doc_gate_codex.evaluate)
            self.assertIs(doc_gate.render_reason, doc_gate_codex.render_reason)
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
