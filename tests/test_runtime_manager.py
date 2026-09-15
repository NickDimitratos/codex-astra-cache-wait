import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/astra-runtime-manager/scripts/manage_runtime.py"
spec = importlib.util.spec_from_file_location("runtime_manager", SCRIPT)
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class RuntimeManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "managed runtime"

    def create_installation(self):
        manager.claim_root(self.root)
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "sample").write_text("test binary content")
        receipt = {"app": str(self.base / "Codex.app"),
                   "files_sha256": manager.hash_tree(runtime),
                   "source_commit": "test", "origin": "test"}
        (self.root / "receipt.json").write_text(json.dumps(receipt))
        return receipt

    def test_status_does_not_create_directory(self):
        self.assertFalse(manager.status(self.root)["installed"])
        self.assertFalse(self.root.exists())

    def test_refuses_unmanaged_directory(self):
        self.root.mkdir()
        (self.root / "notes").write_text("user work")
        with self.assertRaisesRegex(manager.ManagerError, "managed"):
            manager.claim_root(self.root)
        self.assertEqual((self.root / "notes").read_text(), "user work")

    def test_refuses_symlink_root(self):
        other = self.base / "other"
        other.mkdir()
        self.root.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(manager.ManagerError, "symlink"):
            manager.claim_root(self.root)

    def test_modified_runtime_cannot_be_enabled(self):
        self.create_installation()
        (self.root / "runtime/sample").write_text("changed")
        with self.assertRaisesRegex(manager.ManagerError, "checksum"):
            manager.verify_installation(self.root)
        self.assertFalse((self.root / "enabled").exists())

    def test_extra_runtime_files_fail_verification(self):
        self.create_installation()
        (self.root / "runtime/extra").write_text("extra")
        with self.assertRaisesRegex(manager.ManagerError, "checksum"):
            manager.verify_installation(self.root)

    def test_symlink_in_package_rejected(self):
        self.root.mkdir()
        (self.root / "link").symlink_to(self.base / "outside")
        with self.assertRaisesRegex(manager.ManagerError, "symlink"):
            manager.hash_tree(self.root)

    def test_disable_preserves_runtime(self):
        self.create_installation()
        (self.root / "enabled").write_text("yes")
        manager.disable(self.root)
        self.assertFalse((self.root / "enabled").exists())
        self.assertTrue((self.root / "runtime/sample").exists())

    def test_remove_refuses_running_runtime(self):
        self.create_installation()
        with patch.object(manager, "running_commands", return_value=[str(self.root / "runtime/bin/codex")]):
            with self.assertRaisesRegex(manager.ManagerError, "running"):
                manager.remove(self.root)
        self.assertTrue(self.root.exists())

    def test_remove_refuses_unknown_process_state(self):
        self.create_installation()
        with patch.object(manager, "running_commands", side_effect=manager.ManagerError("Cannot inspect running processes")):
            with self.assertRaises(manager.ManagerError):
                manager.remove(self.root)
        self.assertTrue(self.root.exists())

    def test_remove_preserves_unexpected_user_files(self):
        self.create_installation()
        (self.root / "notes").write_text("user work")
        with patch.object(manager, "running_commands", return_value=[]):
            with self.assertRaisesRegex(manager.ManagerError, "Unexpected"):
                manager.remove(self.root)
        self.assertEqual((self.root / "notes").read_text(), "user work")

    def test_remove_only_owned_directory(self):
        self.create_installation()
        outside = self.base / "keep"
        outside.write_text("user work")
        with patch.object(manager, "running_commands", return_value=[]):
            manager.remove(self.root)
        self.assertFalse(self.root.exists())
        self.assertEqual(outside.read_text(), "user work")

    def test_second_operation_is_rejected(self):
        manager.claim_root(self.root)
        with manager.operation_lock(self.root):
            with self.assertRaisesRegex(manager.ManagerError, "operation"):
                with manager.operation_lock(self.root):
                    self.fail("concurrent mutation accepted")
        self.assertFalse((self.root / ".operation-lock").exists())

    def test_enable_rejects_incompatible_app(self):
        self.create_installation()
        with patch.object(manager, "check_app", side_effect=manager.ManagerError("Unsupported Codex version")):
            with self.assertRaisesRegex(manager.ManagerError, "Unsupported"):
                manager.enable(self.root)
        self.assertFalse((self.root / "enabled").exists())

    def test_enable_changes_only_the_launcher_marker(self):
        self.create_installation()
        before = (self.root / "receipt.json").read_bytes()
        with patch.object(manager, "check_app", return_value=manager.SPEC["cli_version"]):
            result = manager.enable(self.root)
        self.assertTrue(result["restart_required"])
        self.assertTrue((self.root / "enabled").exists())
        self.assertEqual((self.root / "receipt.json").read_bytes(), before)

    def test_launch_refuses_an_open_desktop(self):
        receipt = self.create_installation()
        (self.root / "enabled").write_text("yes")
        app_process = receipt["app"] + "/Contents/MacOS/ChatGPT"
        with patch.object(manager, "check_app", return_value=manager.SPEC["cli_version"]), patch.object(manager, "running_commands", return_value=[app_process]):
            with self.assertRaisesRegex(manager.ManagerError, "running"):
                manager.launch(self.root)

    def test_launch_ignores_only_framework_crash_reporters(self):
        receipt = self.create_installation()
        (self.root / "enabled").write_text("yes")
        app = receipt["app"]
        crashpad = app + "/Contents/Frameworks/Codex Framework.framework/Versions/152/Helpers/browser_crashpad_handler"
        with patch.object(manager, "check_app", return_value=manager.SPEC["cli_version"]), patch.object(manager, "running_commands", return_value=[crashpad]), patch.object(manager, "run", return_value="") as launch_command:
            self.assertTrue(manager.launch(self.root)["launch_requested"])
            launch_command.assert_called_once_with(["open", "-a", Path(app), "--env", f"CODEX_CLI_PATH={self.root / 'codex-patched'}"])
        blockers = [
            app + "/Contents/MacOS/ChatGPT",
            app + "/Contents/Resources/codex",
            app + "/Contents/Resources/codex-code-mode-host",
            app + "/Contents/Resources/browser_crashpad_handler",
            app + "/Contents/Frameworks/Codex Framework.framework/Helpers/Codex (Renderer)",
            crashpad + ".other",
            str(self.root / "runtime/bin/codex"),
        ]
        for blocker in blockers:
            with self.subTest(blocker=blocker), patch.object(manager, "check_app", return_value=manager.SPEC["cli_version"]), patch.object(manager, "running_commands", return_value=[crashpad, blocker]), patch.object(manager, "run") as launch_command:
                with self.assertRaisesRegex(manager.ManagerError, "running"):
                    manager.launch(self.root)
                launch_command.assert_not_called()

    def run_desktop_launcher(self, commands):
        # Replace only OS process discovery and app opening, then execute the real shell guard.
        launcher = (self.root / "launch-patched.command").read_text()
        launcher = launcher.replace("processes=$(/bin/ps -axo comm=)", "processes=" + shlex.quote("\n".join(commands)))
        launcher = launcher.replace("exec /usr/bin/open ", "printf '%s\\n' ")
        script = self.root / "launcher-test.command"
        script.write_text(launcher)
        return subprocess.run(["sh", str(script)], capture_output=True, text=True, timeout=10)

    @unittest.skipIf(os.name == "nt", "Desktop shell behavior is tested on POSIX")
    def test_shell_launcher_ignores_crash_reporters_but_blocks_active_workers(self):
        manager.claim_root(self.root)
        app = self.base / "Owner's Codex.app"
        manager.create_launchers(self.root, app)
        (self.root / "enabled").write_text("yes")
        crashpad = str(app) + "/Contents/Frameworks/Codex Framework.framework/Versions/152/Helpers/browser_crashpad_handler"
        result = self.run_desktop_launcher([crashpad])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["-a", str(app), "--env", f"CODEX_CLI_PATH={self.root / 'codex-patched'}"])
        for worker in ("MacOS/ChatGPT", "Resources/codex", "Resources/codex-code-mode-host", "Resources/browser_crashpad_handler", "Frameworks/Codex Framework.framework/Helpers/Codex (Renderer)"):
            with self.subTest(worker=worker):
                result = self.run_desktop_launcher([crashpad, str(app) + "/Contents/" + worker])
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("CODEX_CLI_PATH=", result.stdout)

    @unittest.skipIf(os.name == "nt", "Desktop shell behavior is tested on POSIX")
    def test_enable_refreshes_old_launcher_without_changing_runtime_or_receipt(self):
        receipt = self.create_installation()
        (self.root / "launch-patched.command").write_text("#!/bin/sh\nexit 1\n")
        before = (self.root / "receipt.json").read_bytes()
        with patch.object(manager, "check_app", return_value=manager.SPEC["cli_version"]):
            manager.enable(self.root)
        crashpad = receipt["app"] + "/Contents/Frameworks/Codex Framework.framework/Versions/152/Helpers/browser_crashpad_handler"
        result = self.run_desktop_launcher([crashpad])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "receipt.json").read_bytes(), before)
        self.assertEqual(manager.hash_tree(self.root / "runtime"), receipt["files_sha256"])

    def test_launcher_handles_spaces_and_quotes(self):
        manager.claim_root(self.root)
        manager.create_launchers(self.root, self.base / "Owner's Codex.app")
        for name in ["codex-patched", "launch-patched.command"]:
            manager.run(["sh", "-n", self.root / name])

    def test_root_name_prefix_does_not_block_unrelated_installation(self):
        self.assertFalse(manager.is_active(self.root, [str(self.root) + "-other/runtime/bin/codex"]))

    def test_new_supported_app_version_still_cannot_activate_old_runtime(self):
        self.create_installation()
        with patch.object(manager, "check_app", return_value="codex-cli 9.9.9"):
            with self.assertRaisesRegex(manager.ManagerError, "version changed"):
                manager.enable(self.root)
        self.assertFalse((self.root / "enabled").exists())


if __name__ == "__main__":
    unittest.main()
