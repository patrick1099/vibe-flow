import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "skills/vibe-flow/scripts/collaboration_config.py"
SPEC = importlib.util.spec_from_file_location("collaboration_config", ENTRY)
config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config)


class CollaborationConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / "guide.md").write_text("tool guide", encoding="utf-8")
        self.raw = {
            "version": 1,
            "tools": {"local": {"executable": "some-tool", "version": "1", "docs": "guide.md"}},
            "agents": {"one": {"tool": "local", "selector": "alpha", "model": "model-A", "effort": "medium", "mode": "review"}},
            "roles": {"reviewer": {"agent": "one"}},
            "organizations": {"review": {"mode": "single", "roles": ["reviewer"]}},
        }

    def write(self, raw=None):
        target = self.base / "config.json"
        target.write_text(json.dumps(self.raw if raw is None else raw), encoding="utf-8")
        return target

    def cli(self, *args, env=None):
        environment = dict(os.environ)
        environment.pop("VIBE_FLOW_COLLABORATION_CONFIG", None)
        if env:
            environment.update(env)
        return subprocess.run([sys.executable, str(ENTRY), *map(str,args)], cwd=self.base, env=environment, capture_output=True, encoding="utf-8")

    def test_real_cli_changed_member_model_tool_follow_config(self):
        target = self.write()
        before = self.cli("--config", target, "--organization", "review")
        self.assertEqual(before.returncode, 0, before.stderr)
        self.raw["agents"]["new"] = {**self.raw["agents"]["one"], "selector": "new-selector", "model": "model-B", "effort": "high"}
        self.raw["roles"]["reviewer"]["agent"] = "new"
        self.raw["tools"]["local"]["executable"] = "replacement-tool"
        self.write()
        after = self.cli("--config", target, "--organization", "review")
        self.assertEqual(after.returncode, 0, after.stderr)
        member = json.loads(after.stdout)["data"]["members"]["reviewer"]
        self.assertEqual((member["agent"],member["selector"],member["model"],member["effort"],member["tool_info"]["executable"]), ("new","new-selector","model-B","high","replacement-tool"))
        self.assertNotEqual(before.stdout, after.stdout)

    def test_invalid_values_fail_cli_and_no_output(self):
        mutations = [
            lambda c: c.update(version=2),
            lambda c: c["agents"]["one"].update(model=""),
            lambda c: c["agents"]["one"].update(effort=None),
            lambda c: c["agents"]["one"].update(mode=False),
            lambda c: c["agents"]["one"].update(tool="missing"),
            lambda c: c["roles"]["reviewer"].update(agent="missing"),
            lambda c: c["organizations"]["review"].update(roles=["missing"]),
            lambda c: c["organizations"]["review"].update(mode="automatic"),
            lambda c: c["organizations"]["review"].update(chair="unknown"),
            lambda c: c["tools"]["local"].update(docs="missing.md"),
            lambda c: c["tools"]["local"].update(version=""),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                raw = copy.deepcopy(self.raw)
                mutation(raw)
                result = self.cli("--config", self.write(raw), "--organization", "review")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)

    def test_bad_override_never_uses_bundle(self):
        target = self.base / "broken.json"
        target.write_text("{", encoding="utf-8")
        result = self.cli(env={"VIBE_FLOW_COLLABORATION_CONFIG": str(target)})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        for path in (self.base / "missing.json", ""):
            result = self.cli(env={"VIBE_FLOW_COLLABORATION_CONFIG": str(path)})
            self.assertNotEqual(result.returncode, 0)

    def test_absent_user_override_uses_bundle_but_bad_existing_fails(self):
        with patch.object(Path, "home", return_value=self.base), patch.dict(os.environ, {}, clear=True):
            source, _ = config.load_config()
            self.assertEqual(source, config.SUGGESTIONS)
            override = self.base / ".vibe-flow/collaboration.json"
            override.parent.mkdir()
            override.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                config.load_config()

    def test_resolve_symbols_and_unknown_rejected(self):
        with patch.dict(os.environ, {"TEST_COLLAB_DIR": str(self.base)}):
            self.assertEqual(config.resolve_path("${ENV:TEST_COLLAB_DIR}/guide.md", self.base), self.base / "guide.md")
            self.assertEqual(config.resolve_path("${CONFIG_DIR}/guide.md", self.base), self.base / "guide.md")
            self.assertEqual(config.resolve_path("${PLUGIN_ROOT}/file", self.base), ROOT / "file")
        for value in ("${UNKNOWN}/x", "${ENV:NOT_SET_VIBE_TEST}/x", "$HOME/x", "%HOME%/x"):
            with self.subTest(value=value), self.assertRaises(config.ConfigError):
                config.resolve_path(value,self.base)

    def test_bundle_four_sections_and_brainstorm(self):
        with patch.object(Path, "home", return_value=self.base), patch.dict(os.environ, {}, clear=True):
            _, cfg = config.load_config()
        self.assertTrue(all(key in cfg for key in ("tools","agents","roles","organizations")))
        result = config.describe(cfg,"brainstorm")
        self.assertIn(result["chair"],result["members"])
        self.assertEqual(Path(cfg["tools"]["acpx"]["docs"]), ROOT / "skills/vibe-flow/references/acpx.md")

    def test_unknown_organization_fails(self):
        result = self.cli("--config",self.write(),"--organization","absent")
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,"")

    def test_executable_paths_resolve_and_unknown_symbols_fail(self):
        self.raw["tools"]["local"]["executable"] = "${CONFIG_DIR}/bin/runner"
        result = self.cli("--config", self.write(), "--organization", "review")
        self.assertEqual(result.returncode, 0, result.stderr)
        tool = json.loads(result.stdout)["data"]["members"]["reviewer"]["tool_info"]
        self.assertEqual(Path(tool["executable"]), self.base / "bin/runner")
        for value in ("${UNKNOWN}/runner", "${ENV:VIBE_NOT_SET_TEST}/runner", "$HOME/runner", "%HOME%/runner"):
            self.raw["tools"]["local"]["executable"] = value
            result = self.cli("--config", self.write())
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_missing_unselected_tool_isolated_selected_tool_fails(self):
        self.raw["tools"]["broken"] = {"executable":"missing-tool", "version":"1", "docs":"missing.md"}
        self.raw["agents"]["broken"] = {**self.raw["agents"]["one"], "tool":"broken"}
        self.raw["roles"]["broken"] = {"agent":"broken"}
        self.raw["organizations"]["broken"] = {"mode":"single", "roles":["broken"]}
        path = self.write()
        overview = self.cli("--config", path)
        self.assertEqual(overview.returncode, 0, overview.stderr)
        self.assertFalse(json.loads(overview.stdout)["data"]["tools"]["broken"]["available"])
        healthy = self.cli("--config", path, "--organization", "review")
        self.assertEqual(healthy.returncode, 0, healthy.stderr)
        broken = self.cli("--config", path, "--organization", "broken")
        self.assertNotEqual(broken.returncode, 0)
        self.assertEqual(broken.stdout, "")

    def test_shared_config_has_no_machine_absolute_paths(self):
        text = config.SUGGESTIONS.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"[A-Za-z]:[\\/]")
        self.assertNotIn("/Users/",text)
        self.assertNotIn("/home/",text)

    def test_flow_rules_no_active_retired_cli_or_fixed_seats(self):
        files = ["skills/vibe-flow/SKILL.md", "skills/vibe-flow/references/collaboration.md", "skills/brainstorm/SKILL.md", "skills/brainstorm/agents/openai.yaml", "skills/subagent-foreman/SKILL.md"]
        for rel in files:
            with self.subTest(file=rel):
                text = (ROOT/rel).read_text(encoding="utf-8")
                self.assertNotIn("ai-room",text)
                if "brainstorm" in rel:
                    self.assertNotRegex(text,r"GPT|Opus|codex|claude|acpx")


class UpstreamDocumentLocationTest(unittest.TestCase):
    def test_vendor_not_discoverable_as_plugin_skill(self):
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        discovery_root = ROOT / manifest["skills"]
        discovered = [p.relative_to(ROOT).as_posix() for p in discovery_root.rglob("SKILL.md")]
        self.assertFalse(any("vendor/acpx/" in p for p in discovered), discovered)
        self.assertFalse((ROOT / "skills/vibe-flow/vendor/acpx/SKILL.md").exists())
        self.assertTrue((ROOT / "vendor/acpx/SKILL.md").is_file())

    def test_vendor_matches_pinned_npm_original_hashes(self):
        import hashlib
        expected = {
            "SKILL.md": "6cb199adee79a742e2fa43cb5f4aebf8e6222ade1d5b501fc13308e6f3c2daf4",
            "LICENSE": "5c3dd08185d6d0a0045a45b9aea2fd9d85343f7ed5dbe23915e6f15e7b814f2d",
        }
        for name, digest in expected.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT / "vendor/acpx" / name).read_bytes()).hexdigest(), digest)

    def test_sync_destination_is_plugin_root_vendor(self):
        spec = importlib.util.spec_from_file_location("sync_acpx", ROOT / "skills/vibe-flow/scripts/sync_acpx.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.DEST, ROOT / "vendor/acpx")
        source = json.loads((module.DEST / "SOURCE.json").read_text(encoding="utf-8"))
        self.assertEqual(source["package"], "acpx")
        self.assertEqual(source["version"], "0.22.0")


if __name__ == "__main__":
    unittest.main()
