"""The existing synchronizer can target a second skill without touching its default."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/vibe-apps/scripts/sync_upstream.py"
spec = importlib.util.spec_from_file_location("sync_upstream", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SyncTargetTest(unittest.TestCase):
    def test_selected_vendor_and_check_share_fetch_without_default_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "upstream.json").write_text(json.dumps({"example": {"repo": "owner/repo", "ref": "main",
                "files": {"source.md": "example/source.md"}}}), encoding="utf-8")
            with patch.object(module, "_commit_sha", return_value="123abc"), patch.object(module, "_get", return_value=b"upstream original\n"):
                check = module.run(True, root)
                self.assertEqual(check["outdated"], ["example:example/source.md"])
                self.assertFalse((root / "example").exists())
                sync = module.run(False, root)
                self.assertEqual(sync["updated"], check["outdated"])
                self.assertEqual((root / "example/source.md").read_bytes(), b"upstream original\n")
                lock_before = (root / "upstream.lock.json").read_bytes()
                self.assertEqual(module.run(True, root)["outdated"], [])
                self.assertEqual((root / "upstream.lock.json").read_bytes(), lock_before)
                self.assertEqual(json.loads(lock_before)["example"]["commit"], "123abc")

if __name__ == "__main__": unittest.main()
