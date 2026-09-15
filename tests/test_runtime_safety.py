import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/astra-runtime-manager/scripts"))
import manage_runtime as manager


class RuntimeSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "managed space"
        manager.claim_root(self.root)

    def installed(self, desktop=False):
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "sample").write_text("owned fixture")
        receipt = {"app": str(self.base / "Codex.app") if desktop else None,
                   "cli": str(self.base / "original"), "cli_version": manager.SPEC["cli_version"],
                   "files_sha256": manager.hash_tree(runtime), "origin": "fixture"}
        (self.root / "receipt.json").write_text(json.dumps(receipt))
        return receipt

    def test_enable_rejects_each_symlink_before_changing_any_output(self):
        self.installed(desktop=True)
        outputs = ("enabled", "codex-patched", "codex-patched.py", "launch-patched.command")
        for name in outputs:
            (self.root / name).write_text("old " + name)
        for name in outputs:
            with self.subTest(name=name):
                target = self.base / "unrelated-note"
                target.write_text("preserve this")
                target.chmod(0o600)
                previous_mode = target.stat().st_mode
                output = self.root / name
                output.unlink()
                output.symlink_to(target)
                before = {n: (self.root / n).read_bytes() for n in outputs}
                with patch.object(manager, "check_receipt_app"):
                    with self.assertRaisesRegex(manager.ManagerError, "symlink"):
                        manager.enable(self.root)
                self.assertEqual(target.read_text(), "preserve this")
                self.assertEqual(target.stat().st_mode, previous_mode)
                self.assertEqual({n: (self.root / n).read_bytes() for n in outputs}, before)
                output.unlink()
                output.write_text("old " + name)

    def test_json_writer_does_not_follow_predictable_temporary_symlink(self):
        outside = self.base / "unrelated"
        outside.write_text("preserve")
        (self.root / "receipt.json.tmp").symlink_to(outside)
        manager.write_json(self.root / "receipt.json", {"fixture": True})
        self.assertEqual(outside.read_text(), "preserve")
        self.assertEqual(json.loads((self.root / "receipt.json").read_text()), {"fixture": True})

    def test_remove_preserves_unexpected_validation_files_and_directories(self):
        for index, name in enumerate(("my-notes.txt", "nested/my-notes.txt", "package-smoke.json/my-notes.txt")):
            with self.subTest(name=name):
                self.root = self.base / str(index)
                manager.claim_root(self.root)
                self.installed()
                validation = self.root / "validation"
                validation.mkdir()
                note = validation / name
                note.parent.mkdir(parents=True, exist_ok=True)
                note.write_text("preserve this")
                with patch.object(manager, "running_commands", return_value=[]):
                    with self.assertRaisesRegex(manager.ManagerError, "Unexpected"):
                        manager.remove(self.root)
                self.assertEqual(note.read_text(), "preserve this")
                note.unlink()
                if note.parent != validation:
                    note.parent.rmdir()

    def test_remove_accepts_only_known_validation_artifacts(self):
        self.installed()
        validation = self.root / "validation"
        validation.mkdir()
        for name in ("package-smoke.json", "package-smoke.stdout.log", "package-smoke.stderr.log",
                     "app-server-smoke.json", "app-server-smoke.stderr.log"):
            (validation / name).write_text("fixture")
        with patch.object(manager, "running_commands", return_value=[]):
            self.assertTrue(manager.remove(self.root)["removed"])

    def portable_fixture(self):
        original = self.base / "original.py"
        original.write_text('import json, sys\nprint("codex-cli 0.154.0-alpha.6.2" if sys.argv[1:] == ["--version"] else json.dumps(["original"] + sys.argv[1:]))\n')
        binary = self.root / "runtime/bin/codex.py"
        binary.parent.mkdir(parents=True)
        binary.write_text('import json, sys\nprint(json.dumps(["patched"] + sys.argv[1:]))\n')
        (binary.parent / "helper").write_text("owned helper")
        specification = {"original_command": [sys.executable, str(original)],
                         "patched_command": [sys.executable, str(binary)],
                         "cli_version": manager.SPEC["cli_version"], "features": []}
        manager.write_portable_launcher(self.root, specification)
        (self.root / "receipt.json").write_text(json.dumps({"files_sha256": manager.hash_tree(self.root / "runtime")}))
        (self.root / "enabled").write_text("enabled")
        return binary

    def test_portable_launcher_checks_cli_helpers_and_ownership(self):
        binary = self.portable_fixture()
        command = [sys.executable, str(self.root / "codex-patched.py"), "literal & $text"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), ["patched", "literal & $text"])
        for path in (binary, binary.parent / "helper", self.root / "owner.json", self.root / "receipt.json"):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                path.write_text('print(\'["MODIFIED_FIXTURE_EXECUTED"]\')')
                result = subprocess.run(command, capture_output=True, text=True)
                path.write_bytes(before)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), ["original", "literal & $text"])
                self.assertTrue(result.stderr.strip())

    @unittest.skipIf(os.name == "nt", "Desktop wrapper requires a POSIX shell")
    def test_shell_wrapper_checks_cli_and_helpers(self):
        app = self.base / "Owner's Codex.app"
        original = app / "Contents/Resources/codex"
        original.parent.mkdir(parents=True)
        original.write_text('#!/bin/sh\nif [ "${1-}" = --version ]; then echo "codex-cli 0.154.0-alpha.6.2"; else printf "original\\n%s\\n" "$@"; fi\n')
        original.chmod(0o755)
        binary = self.root / "runtime/bin/codex"
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\necho patched\n')
        binary.chmod(0o755)
        helper = binary.parent / "codex-code-mode-host"
        helper.write_text("owned helper")
        manager.create_launchers(self.root, app)
        (self.root / "receipt.json").write_text(json.dumps({"files_sha256": manager.hash_tree(self.root / "runtime")}))
        (self.root / "enabled").write_text("enabled")
        command = ["sh", str(self.root / "codex-patched"), "literal & $text"]
        self.assertEqual(subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip(), "patched")
        for path in (binary, helper):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                path.write_text('#!/bin/sh\necho MODIFIED_FIXTURE_EXECUTED\n')
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                path.write_bytes(before)
                self.assertEqual(result.stdout.splitlines(), ["original", "literal & $text"])
                self.assertTrue(result.stderr.strip())

    def package_fixture(self):
        package = self.base / "package"
        for name in manager.PACKAGE_FILES:
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
        metadata = {"target":"aarch64-apple-darwin", "entrypoint":"bin/codex", "variant":"codex",
                    "layoutVersion":1, "version":"0.154.0-alpha.6.2+astra-cache-wait.1"}
        (package / "codex-package.json").write_text(json.dumps(metadata))
        installation = {"app":None, "cli":str(self.base / "original"),
                        "release":{"id":"fixture", "spec":manager.SPEC, "package_version":metadata["version"]}}
        return package, installation

    def validate_fixture(self, arguments, **kwargs):
        # Only external smoke subprocesses are replaced. Copying, hashes, writes and promotion stay real.
        output = Path(arguments[-1])
        name = "package-smoke.json" if Path(arguments[1]).name == "package_smoke.py" else "app-server-smoke.json"
        (output / name).write_text('{"passed":true}')
        return ""

    def test_launcher_and_receipt_write_failures_leave_setup_retryable(self):
        package, installation = self.package_fixture()
        for writer in ("write_portable_launcher", "write_json"):
            with self.subTest(writer=writer):
                self.root = self.base / writer
                manager.claim_root(self.root)
                with patch.object(manager, "run", side_effect=self.validate_fixture):
                    with patch.object(manager, writer, side_effect=OSError("synthetic write failure")):
                        with self.assertRaises((OSError, manager.ManagerError)):
                            manager.install_package(self.root, package, installation=installation)
                    for name in ("runtime", "receipt.json", "enabled"):
                        self.assertFalse((self.root / name).exists(), name)
                    self.assertTrue(manager.install_package(self.root, package, installation=installation)["installed"])
                    self.assertTrue(manager.verify_installation(self.root))
                with patch.object(manager, "running_commands", return_value=[]):
                    manager.remove(self.root)
                manager.claim_root(self.root)

    def test_failed_promotion_restores_existing_owned_outputs(self):
        package, installation = self.package_fixture()
        launcher = self.root / "codex-patched.py"
        launcher.write_text("old launcher")
        replace = Path.replace
        def fail_runtime_promotion(source, target):
            if Path(target) == self.root / "runtime":
                raise OSError("synthetic promotion failure")
            return replace(source, target)
        with patch.object(manager, "run", side_effect=self.validate_fixture), patch.object(Path, "replace", fail_runtime_promotion):
            with self.assertRaises((OSError, manager.ManagerError)):
                manager.install_package(self.root, package, installation=installation)
        self.assertEqual(launcher.read_text(), "old launcher")
        self.assertFalse((self.root / "receipt.json").exists())
        self.assertFalse((self.root / "runtime").exists())

    def test_promotion_refusal_also_rolls_back_previously_promoted_outputs(self):
        package, installation = self.package_fixture()
        external = self.base / "preserve"
        external.write_text("unrelated work")
        replace = Path.replace
        def introduce_symlink(source, target):
            result = replace(source, target)
            if Path(target) == self.root / "validation":
                (self.root / "codex-patched.py").symlink_to(external)
            return result
        with patch.object(manager, "run", side_effect=self.validate_fixture), patch.object(Path, "replace", introduce_symlink):
            with self.assertRaises(manager.ManagerError):
                manager.install_package(self.root, package, installation=installation)
        self.assertEqual(external.read_text(), "unrelated work")
        self.assertFalse((self.root / "validation").exists())
        self.assertFalse((self.root / "runtime").exists())

    @unittest.skipIf(os.name == "nt", "Executable mode bits are POSIX behavior")
    def test_nonexecutable_patched_cli_falls_back_without_losing_arguments(self):
        self.portable_fixture()
        binary = self.root / "runtime/bin/codex"
        binary.write_text('#!/bin/sh\necho patched\n')
        binary.chmod(0o600)
        original = self.base / "original.py"
        manager.write_portable_launcher(self.root, {"original_command":[sys.executable, str(original)],
            "patched_command":[str(binary)], "cli_version":manager.SPEC["cli_version"], "features":[]})
        (self.root / "receipt.json").write_text(json.dumps({"files_sha256":manager.hash_tree(self.root / "runtime")}))
        result = subprocess.run([sys.executable, str(self.root / "codex-patched.py"), "literal"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["original", "literal"])

    def test_failed_rollback_retains_staging_even_without_previous_installation(self):
        package, installation = self.package_fixture()
        replace = Path.replace
        def fail_promotion_and_rollback(source, target):
            if Path(target) == self.root / "runtime" or source == self.root / "codex-patched.py":
                raise OSError("synthetic repeated I/O failure")
            return replace(source, target)
        with patch.object(manager, "run", side_effect=self.validate_fixture), patch.object(Path, "replace", fail_promotion_and_rollback):
            with self.assertRaisesRegex(manager.ManagerError, "recovery needs inspection"):
                manager.install_package(self.root, package, installation=installation)
        staging = list(self.root.glob(".staging-*"))
        self.assertEqual(len(staging), 1)
        self.assertTrue((staging[0] / "runtime/bin/codex").is_file())
        self.assertTrue((staging[0] / "receipt.json").is_file())
        self.assertFalse((self.root / "enabled").exists())


if __name__ == "__main__":
    unittest.main()
