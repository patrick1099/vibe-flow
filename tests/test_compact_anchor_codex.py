"""Codex 原生事件适配回归：临时状态和真实脚本，不冒充宿主端到端验收。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks/compact_anchor_codex.py"


class CodexCompactAnchorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="vibe-compact-")
        self.root = Path(self.tmp.name)
        self.data = self.root / "plugin-data"
        self.cwd = self.root / "firmware"
        self.cwd.mkdir()
        self.env = dict(os.environ, PLUGIN_DATA=str(self.data), VIBE_FLOW_DOC_GATE_HOME=str(self.root))

    def tearDown(self):
        self.tmp.cleanup()

    def project(self, name="personal"):
        p = self.root / name
        (p / "docs").mkdir(parents=True)
        (p / "docs/HANDOFF.md").write_text("# Handoff\n\n## 已谈定\n- KEEP_" + name +
                                         "\n\n## 在做\nNOT_AGREED\n", encoding="utf-8")
        return p

    def event(self, event, **fields):
        return dict(session_id="s1", cwd=str(self.cwd), hook_event_name=event, **fields)

    def run_hook(self, event, code=0):
        p = subprocess.run([sys.executable, "-B", str(HOOK)], input=json.dumps(event, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", env=self.env)
        self.assertEqual(p.returncode, code, p.stderr)
        return json.loads(p.stdout) if p.stdout.strip() else None

    def patch(self, path, sid="s1", call="patch1", success=True):
        d = self.event("PostToolUse", turn_id="t1", tool_name="apply_patch", tool_use_id=call,
                       tool_input={"command": ""},
                       tool_response="Exit code: " + ("0" if success else "1") +
                       "\nOutput:\nSuccess. Updated the following files:\nM " + str(path) + "\n")
        d["session_id"] = sid
        self.assertIsNone(self.run_hook(d))

    def compact(self, **fields):
        d = self.event("SessionStart", source="compact")
        d.update(fields)
        out = self.run_hook(d)
        return out["hookSpecificOutput"]["additionalContext"] if out else ""

    def test_successful_patch_restores_cross_repository_context(self):
        p = self.project()
        self.patch(p / "main.py")
        text = self.compact()
        self.assertIn("KEEP_personal", text)
        self.assertNotIn("NOT_AGREED", text)
        self.assertIn("KEEP_personal", self.compact())

    def test_failed_patch_is_not_write_evidence(self):
        p = self.project()
        self.patch(p / "main.py", success=False)
        self.assertEqual(self.compact(), "")

    def test_native_bash_path_is_only_listed_without_write_evidence(self):
        p = self.project()
        self.run_hook(self.event("PostToolUse", turn_id="t1", tool_name="Bash", tool_use_id="shell1",
                      tool_input={"command": f'Get-Content "{p / "main.py"}"'}, tool_response="x\r\n"))
        text = self.compact()
        self.assertIn(str(p / "docs/HANDOFF.md"), text)
        self.assertNotIn("KEEP_personal", text)

    def test_real_worktree_evidence_survives_deleted_worktree(self):
        p = self.project()
        (p / ".git").mkdir()
        wt = self.root / "gone"
        self.run_hook(self.event("PostToolUse", turn_id="t1", tool_name="Bash", tool_use_id="shell1",
                      tool_input={"command": f'git -C "{p}" worktree add "{wt}" -b feature'},
                      tool_response={"stdout": "created", "exit_code": 0}))
        self.patch(wt / "main.py")
        self.assertIn("KEEP_personal", self.compact())

    def test_session_end_cleans_only_its_own_records(self):
        p = self.project()
        self.patch(p / "main.py")
        self.patch(p / "main.py", sid="s2")
        self.run_hook(self.event("SessionEnd"))
        self.assertEqual(self.compact(), "")
        self.assertIn("KEEP_personal", self.compact(session_id="s2"))

    def test_no_turn_id_needed_at_compaction(self):
        p = self.project()
        self.assertIn("KEEP_personal", self.compact(cwd=str(p)))

    def test_noncompact_start_does_not_inject(self):
        p = self.project()
        for source in ("startup", "resume", "clear"):
            d = self.event("SessionStart", source=source)
            d["cwd"] = str(p)
            self.assertIsNone(self.run_hook(d))

    def test_corrupt_record_is_visible_error(self):
        p = self.project()
        self.patch(p / "main.py")
        next(self.data.rglob("*.json")).write_text("{}", encoding="utf-8")
        self.run_hook(self.event("SessionStart", source="compact"), code=1)


if __name__ == "__main__":
    unittest.main()
