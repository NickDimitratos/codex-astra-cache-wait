import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/astra-runtime-manager/scripts/compatibility.py"
spec = importlib.util.spec_from_file_location("compatibility_checks", SCRIPT)
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)


class CompatibilityTests(unittest.TestCase):
    def test_exact_release_matches_only_tested_platform(self):
        version = "codex-cli 0.154.0-alpha.6.2"
        self.assertIsNotNone(compat.select_release(version, "Darwin", "arm64"))
        for system, machine in [("Linux", "aarch64"), ("Windows", "AMD64"), ("Darwin", "x86_64")]:
            self.assertIsNone(compat.select_release(version, system, machine))

    def test_unknown_stable_prerelease_and_custom_build_never_select_patch(self):
        for version in ["0.153.4", "0.154.0", "0.154.0-alpha.6.3", "0.154.0-alpha.6.2+custom", "9.0.0"]:
            self.assertIsNone(compat.select_release("codex-cli " + version, "Darwin", "arm64"))

    def test_old_cli_gets_json_reporting_without_plugin_support(self):
        with patch.object(compat, "probe", side_effect=["codex-cli 0.99.0", "Commands:\n  exec Execute\n", "Options:\n --json"]):
            result = compat.inspect_cli(Path("codex"))
        self.assertFalse(result["native_plugins"])
        self.assertTrue(result["exec_json"])
        self.assertFalse(result["runtime_patch_available"])

    def test_future_cli_can_have_plugins_without_approved_runtime(self):
        with patch.object(compat, "probe", side_effect=["codex-cli 9.0.0", "Commands:\n  exec Execute\n  plugin Manage\n", " --json"]):
            result = compat.inspect_cli(Path("codex"))
        self.assertTrue(result["native_plugins"])
        self.assertTrue(result["exec_json"])
        self.assertFalse(result["runtime_patch_available"])

    def test_probe_failure_is_unknown_not_supported(self):
        with patch.object(compat, "probe", side_effect=subprocess.TimeoutExpired("codex", 15)):
            result = compat.inspect_cli(Path("codex"))
        self.assertIsNone(result["native_plugins"])
        self.assertFalse(result["runtime_patch_available"])

    def test_ambiguous_desktop_requires_explicit_selection(self):
        with patch.object(compat, "app_candidates", return_value=[Path("one.app"), Path("two.app")]):
            with self.assertRaisesRegex(ValueError, "--app"):
                compat.discover_app()

    def test_catalog_rejects_escape_and_duplicate_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "runtime-releases.json"
            path.write_text(json.dumps({"schema_version": 1, "releases": [{"manifest": "../escape.json"}]}))
            with self.assertRaisesRegex(ValueError, "inside"):
                compat.catalog(root)
            item = {"id": "test", "manifest": "v.json", "system": "Darwin", "machine": "arm64"}
            (root / "v.json").write_text(json.dumps({"cli_version": "codex-cli 1.0.0"}))
            path.write_text(json.dumps({"schema_version": 1, "releases": [item, item]}))
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                compat.catalog(root)


if __name__ == "__main__":
    unittest.main()
