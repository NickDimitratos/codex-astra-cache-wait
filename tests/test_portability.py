import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
import io

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/astra-runtime-manager/scripts'
sys.path.insert(0, str(SCRIPTS))
import compatibility
import manage_runtime as manager
import runtime_platform


class PortabilityTests(unittest.TestCase):
    def test_cpu_alias_does_not_hide_tested_apple_runtime(self):
        self.assertIsNotNone(compatibility.select_release('codex-cli 0.154.0-alpha.6.2', 'Darwin', 'aarch64'))

    def test_native_target_matches_os_cpu_and_linux_abi(self):
        cases = [
            ('Darwin', 'ARM64', '', 'aarch64-apple-darwin'),
            ('Darwin', 'amd64', '', 'x86_64-apple-darwin'),
            ('Windows', 'AMD64', '', 'x86_64-pc-windows-msvc'),
            ('Windows', 'aarch64', '', 'aarch64-pc-windows-msvc'),
            ('Linux', 'x86_64', 'glibc', 'x86_64-unknown-linux-gnu'),
            ('Linux', 'arm64', 'glibc', 'aarch64-unknown-linux-gnu'),
            ('Linux', 'x86_64', 'musl', 'x86_64-unknown-linux-musl'),
            ('Linux', 'aarch64', 'musl', 'aarch64-unknown-linux-musl'),
        ]
        for system, cpu, libc, expected in cases:
            with self.subTest(system=system, cpu=cpu, libc=libc):
                self.assertEqual(compatibility.native_target(system, cpu, libc), expected)
        for system, cpu in [('Linux', 'i686'), ('Linux', 'riscv64'), ('FreeBSD', 'x86_64')]:
            self.assertIsNone(compatibility.native_target(system, cpu, 'glibc'))

    def test_source_checked_targets_require_explicit_experimental_opt_in(self):
        self.assertIsNone(compatibility.select_release('codex-cli 0.154.0', 'Linux', 'AMD64'))
        release = compatibility.select_release('codex-cli 0.154.0', 'Linux', 'AMD64', experimental=True)
        self.assertEqual(release['spec']['tested_target'], 'x86_64-unknown-linux-gnu')
        self.assertEqual(release['validation'], 'local_validation_required')
        self.assertEqual(release['spec']['commit'], '6b9826e3aa83b1a5947db50f4332cb9c65f1b340')

    def test_windows_layout_preserves_sandbox_helpers(self):
        files = manager.package_files('x86_64-pc-windows-msvc')
        self.assertIn('bin/codex.exe', files)
        self.assertIn('codex-resources/codex-command-runner.exe', files)
        self.assertIn('codex-resources/codex-windows-sandbox-setup.exe', files)
        self.assertNotIn('codex-resources/zsh/bin/zsh', files)
        self.assertIn('codex-resources/bwrap', manager.package_files('aarch64-unknown-linux-musl'))

    def test_standalone_cli_preflight_does_not_require_desktop(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / 'codex'
            binary.write_text('native fixture')
            with patch.object(compatibility, 'probe', return_value='codex-cli 0.154.0'), \
                 patch.object(compatibility.platform, 'system', return_value='Linux'), \
                 patch.object(compatibility.platform, 'machine', return_value='x86_64'):
                install = manager.resolve_installation(None, str(binary), experimental=True)
            self.assertIsNone(install['app'])
            self.assertEqual(install['cli'], str(binary.resolve()))
            self.assertEqual(install['version'], 'codex-cli 0.154.0')

    def test_launcher_forwards_literal_arguments_and_falls_back_after_upgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'managed space'
            root.mkdir()
            original = Path(temporary) / 'original.py'
            binary = root / 'runtime/bin/codex.py'
            binary.parent.mkdir(parents=True)
            original.write_text('import json, sys\nprint("codex-cli 0.154.0" if sys.argv[1:] == ["--version"] else json.dumps(["original"] + sys.argv[1:]))\n')
            binary.write_text('import json, sys\nprint(json.dumps(["patched"] + sys.argv[1:]))\n')
            launcher_spec = {'original_command': [sys.executable, str(original)],
                             'patched_command': [sys.executable, str(binary)],
                             'cli_version': 'codex-cli 0.154.0',
                             'features': ['reasoning_effort_override', 'event_driven_wait']}
            manager.write_portable_launcher(root, launcher_spec)
            (root / 'enabled').write_text('enabled')
            (root / 'receipt.json').write_text('{}')
            args = ['exec', 'spaces and "quotes" & $HOME', '--json']
            command = [sys.executable, str(root / 'codex-patched.py')] + args
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), ['patched', '--enable', 'reasoning_effort_override', '--enable', 'event_driven_wait'] + args)
            original.write_text(original.read_text().replace('0.154.0', '0.155.0'))
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), ['original'] + args)
            self.assertFalse((root / 'unexpected').exists())

    def test_standalone_receipt_checks_original_cli_after_update(self):
        receipt = {'app': None, 'cli': '/native/codex', 'cli_version': 'codex-cli 0.154.0'}
        with patch.object(compatibility, 'probe', return_value='codex-cli 0.155.0'):
            with self.assertRaisesRegex(manager.ManagerError, 'version changed'):
                manager.check_receipt_app(receipt)

    def test_unknown_cli_cannot_create_managed_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'managed'
            with patch.object(sys, 'argv', ['manager', 'setup', '--cli', str(Path(temporary)/'missing'), '--root', str(root), '--experimental']), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    manager.main()
            self.assertEqual(stopped.exception.code, 1)
            self.assertFalse(root.exists())

    def test_windows_setup_requires_native_executable_before_probing(self):
        with tempfile.TemporaryDirectory() as temporary:
            shim = Path(temporary)/'codex.cmd'
            shim.write_text('package manager shim')
            with patch.object(manager.platform, 'system', return_value='Windows'):
                with self.assertRaisesRegex(manager.ManagerError, 'native codex.exe'):
                    manager.resolve_installation(cli=str(shim), experimental=True)

    def test_linux_process_detection_uses_executable_path_not_comm_basename(self):
        if os.name == 'nt':
            self.skipTest('Linux procfs symlink representation')
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)
            process = proc/'123'
            process.mkdir()
            (process/'comm').write_text('codex\n')
            (process/'exe').symlink_to('/managed/runtime/bin/codex')
            self.assertEqual(runtime_platform.linux_executables(proc), ['/managed/runtime/bin/codex'])

    def test_windows_hidden_codex_process_is_unknown_instead_of_inactive(self):
        with self.assertRaisesRegex(ValueError, 'unknown'):
            runtime_platform.windows_executables([{'Name':'codex.exe','ExecutablePath':None}])
        self.assertEqual(runtime_platform.windows_executables([
            {'Name':'System','ExecutablePath':None},
            {'Name':'codex-code-mode-host.exe','ExecutablePath':r'C:\managed\runtime\bin\codex-code-mode-host.exe'}]),
            [r'C:\managed\runtime\bin\codex-code-mode-host.exe'])

    def test_explicit_target_cannot_cross_os_or_cpu(self):
        self.assertIsNone(compatibility.select_release('codex-cli 0.154.0', 'Linux', 'x86_64', experimental=True, target='aarch64-pc-windows-msvc'))

    def test_custom_version_still_gets_capability_detection(self):
        with patch.object(compatibility, 'probe', side_effect=['codex vendor-build', '  exec Execute\n  plugin Manage', '--json']):
            result = compatibility.inspect_cli(Path('codex'))
        self.assertTrue(result['exec_json'])
        self.assertTrue(result['native_plugins'])
        self.assertFalse(result['runtime_patch_available'])
        self.assertFalse(result['experimental_build_available'])

    def test_unrecognized_future_release_never_inherits_upstream_fix_claim(self):
        with patch.object(compatibility, 'probe', side_effect=['codex-cli 9.0.0', '  exec Execute', '--json']):
            result = compatibility.inspect_cli(Path('codex'))
        self.assertIsNone(result['upstream_evidence'])

    def test_platform_packages_are_validated_before_receipt_or_enable(self):
        for target, entrypoint, helper in [
            ('x86_64-pc-windows-msvc','bin/codex.exe','codex-resources/codex-command-runner.exe'),
            ('aarch64-unknown-linux-musl','bin/codex','codex-resources/bwrap')]:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root, package = base/'managed', base/'package'
                manager.claim_root(root)
                for name in manager.package_files(target):
                    path = package/name
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text('fixture')
                metadata = {'target':target,'entrypoint':entrypoint,'variant':'codex','layoutVersion':1,'version':'0.154.0+astra-cache-wait.1'}
                (package/'codex-package.json').write_text(json.dumps(metadata))
                spec = dict(manager.SPEC, tested_target=target, cli_version='codex-cli 0.154.0')
                installation = {'app':None,'cli':str(base/'original'),'release':{'id':'fixture','spec':spec,'package_version':metadata['version']}}
                def validate(arguments, **kwargs):
                    candidate = Path(arguments[2])
                    self.assertTrue((candidate/helper).is_file())
                    self.assertFalse((root/'receipt.json').exists())
                    self.assertFalse((root/'enabled').exists())
                    output = Path(arguments[-1])
                    name = 'package-smoke.json' if Path(arguments[1]).name=='package_smoke.py' else 'app-server-smoke.json'
                    (output/name).write_text('{"passed":true}')
                    return ''
                with patch.object(manager, 'run', side_effect=validate):
                    manager.install_package(root, package, installation=installation)
                receipt = manager.verify_installation(root)
                self.assertIn(helper, receipt['files_sha256'])
                self.assertEqual(receipt['target'], target)
                self.assertFalse((root/'enabled').exists())
                self.assertTrue((root/'codex-patched.py').is_file())

    def test_failed_package_validation_never_installs_or_enables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, package = Path(temporary)/'managed', Path(temporary)/'package'
            manager.claim_root(root)
            for name in manager.PACKAGE_FILES:
                path = package/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            metadata = {'target':'aarch64-apple-darwin','entrypoint':'bin/codex','variant':'codex','layoutVersion':1,'version':'0.154.0-alpha.6.2+astra-cache-wait.1'}
            (package/'codex-package.json').write_text(json.dumps(metadata))
            release={'id':'fixture','spec':manager.SPEC,'package_version':metadata['version']}
            with patch.object(manager, 'run', side_effect=manager.ManagerError('validation failed')):
                with self.assertRaisesRegex(manager.ManagerError, 'validation failed'):
                    manager.install_package(root, package, installation={'app':None,'cli':'original','release':release})
            for name in ('receipt.json','enabled','runtime'):
                self.assertFalse((root/name).exists())


if __name__ == '__main__':
    unittest.main()
