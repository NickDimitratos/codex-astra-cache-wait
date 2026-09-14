#!/usr/bin/env python3
"""Manage a separate experimental Codex runtime. Never replace the desktop app."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compatibility
import runtime_platform

RESOURCES = Path(__file__).resolve().parents[1] / "resources"
SPEC = json.loads((RESOURCES / "compatibility.json").read_text())
OWNER = {"owner": "astra-runtime-manager", "schema": 1}
PACKAGE_FILES = ("codex-package.json", "bin/codex", "bin/codex-code-mode-host",
                 "codex-path/rg", "codex-resources/zsh/bin/zsh")
DEFAULT_ROOT = Path.home() / ".local/share/codex-astra-cache-wait"


class ManagerError(Exception):
    pass


def run(arguments, **kwargs):
    try:
        result = subprocess.run([str(value) for value in arguments], capture_output=True,
                                text=True, **kwargs)
    except subprocess.TimeoutExpired as error:
        raise ManagerError("Command timed out; runtime validation is incomplete") from error
    if result.returncode:
        raise ManagerError((result.stderr or result.stdout or "Command failed")[-2500:].strip())
    return result.stdout.strip()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def require_owner(root):
    if root.is_symlink():
        raise ManagerError("Refusing a symlink as the managed directory")
    marker = root / "owner.json"
    if marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != OWNER:
        raise ManagerError("This directory is not owned by the managed runtime")


def claim_root(root):
    if root.is_symlink():
        raise ManagerError("Refusing a symlink as the managed directory")
    if root.exists():
        require_owner(root)
    else:
        root.mkdir(parents=True, mode=0o700)
        write_json(root / "owner.json", OWNER)


@contextmanager
def operation_lock(root):
    lock = root / ".operation-lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ManagerError("Another operation is in progress; inspect it before removing a stale lock")
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


def hash_tree(root):
    if root.is_symlink():
        raise ManagerError("Package root is a symlink")
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ManagerError("Package contains a symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ManagerError("Package contains an unsupported file type")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def running_commands():
    try:
        return runtime_platform.running_executables()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise ManagerError("Cannot inspect running processes: " + str(error)) from error


def is_active(root, commands):
    prefixes = tuple(os.path.normcase(str(path)) + os.sep for path in (root.absolute(), root.resolve()))
    return any(os.path.normcase(command.strip()).startswith(prefixes) for command in commands)


def package_files(target):
    compatibility.target_identity(target)
    windows = "windows" in target
    suffix = ".exe" if windows else ""
    files = ["codex-package.json", "bin/codex" + suffix,
             "bin/codex-code-mode-host" + suffix, "codex-path/rg" + suffix]
    if windows:
        files += ["codex-resources/codex-command-runner.exe", "codex-resources/codex-windows-sandbox-setup.exe"]
    else:
        files += ["codex-resources/zsh/bin/zsh"]
    if "linux" in target:
        files += ["codex-resources/bwrap"]
    return tuple(files)


def resolve_installation(app=None, cli=None, *, experimental=False, target=None):
    if app is not None and cli is not None:
        raise ManagerError("Choose --app for desktop or --cli for standalone setup")
    selected_app = None
    if cli:
        binary = Path(shutil.which(str(cli)) or cli).expanduser().resolve(strict=True)
    else:
        selected_app = compatibility.discover_app(app)
        binary = selected_app / "Contents/Resources/codex"
    if platform.system() == "Windows" and binary.suffix.lower() != ".exe":
        raise ManagerError("Windows runtime setup needs the native codex.exe, not a .cmd or PowerShell shim")
    version = compatibility.probe(binary, ["--version"])
    release = compatibility.select_release(version, experimental=experimental, target=target)
    if release is None:
        raise ManagerError("No approved runtime path for this CLI/CPU: " + version +
                           ". Run doctor; source-checked candidates require --experimental.")
    if selected_app is not None and platform.system() != "Darwin":
        raise ManagerError("Desktop integration is macOS-only; use --cli for a standalone installation")
    host = selected_app / "Contents/Resources/codex-code-mode-host" if selected_app else None
    if host is not None and not host.is_file():
        raise ManagerError("The selected app must contain its matching Code Mode host")
    return {"app": str(selected_app) if selected_app else None, "cli": str(binary),
            "version": version, "release": release, "host": str(host) if host else None}


def check_app(app):
    binary = app / "Contents/Resources/codex"
    host = app / "Contents/Resources/codex-code-mode-host"
    if not binary.is_file() or not host.is_file():
        raise ManagerError("The selected app must contain Codex and its Code Mode host")
    with tempfile.TemporaryDirectory(prefix="astra-version-") as temporary:
        env = os.environ.copy()
        env["CODEX_HOME"] = temporary
        version = run([binary, "--version"], env=env)
    if compatibility.select_release(version) is None:
        raise ManagerError(f"Unsupported Codex version/platform for runtime activation: {version}. "
                           "Run doctor for available capabilities. Usage reports remain available.")
    return version


def app_release(app):
    version = check_app(app)
    return compatibility.select_release(version)


def check_receipt_app(receipt):
    if receipt.get("cli"):
        try:
            version = compatibility.probe(Path(receipt["cli"]), ["--version"])
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise ManagerError("Original CLI is unavailable; inspect the installation") from error
    else:
        version = check_app(Path(receipt["app"]))
    if version != receipt.get("cli_version", SPEC["cli_version"]):
        raise ManagerError("The app or CLI version changed since installation; the existing runtime must not be activated")
    if receipt.get("target") and compatibility.select_release(version, experimental=True, target=receipt["target"]) is None:
        raise ManagerError("Installed runtime target no longer matches this host or release catalog")


def verify_installation(root):
    require_owner(root)
    receipt_path = root / "receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ManagerError("No validated installation is recorded")
    receipt = json.loads(receipt_path.read_text())
    if hash_tree(root / "runtime") != receipt["files_sha256"]:
        raise ManagerError("Installed runtime checksum verification failed")
    return receipt


def status(root):
    result = {"installed": False, "enabled_for_launcher": False, "running": False,
              "supported_platform": compatibility.native_target() is not None,
              "native_target": compatibility.native_target(),
              "expected_cli": SPEC["cli_version"], "managed_directory": str(root),
              "live_savings_verified": False}
    if not root.exists():
        return result
    require_owner(root)
    if not (root / "receipt.json").is_file():
        result["state"] = "setup_incomplete"
        return result
    receipt = verify_installation(root)
    result.update({"installed": True, "enabled_for_launcher": (root / "enabled").is_file(),
                   "launcher": str(root / ("launch-patched.command" if receipt.get("app") else "codex-patched.py")), "origin": receipt["origin"],
                   "integration": "desktop" if receipt.get("app") else "standalone_cli",
                   "validation_scope": receipt.get("validation_scope", "local_package_checks"),
                   "expected_cli": receipt.get("cli_version", SPEC["cli_version"])})
    try:
        result["running"] = is_active(root, running_commands())
    except ManagerError:
        result["running"] = None
        result["process_status"] = "unknown: process inspection was unavailable"
    try:
        check_receipt_app(receipt)
        result["app_compatible"] = True
    except ManagerError as error:
        result["app_compatible"] = False
        result["compatibility_note"] = str(error)
    return result


def create_launchers(root, app, release=None):
    spec = release["spec"] if release else SPEC
    bundled = shlex.quote(str(app / "Contents/Resources/codex"))
    wrapper = f'''#!/bin/sh
set -eu
managed_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bundled={bundled}
if [ ! -f "$managed_dir/enabled" ] || [ ! -f "$managed_dir/receipt.json" ] ||
   [ ! -x "$managed_dir/runtime/bin/codex" ] ||
   [ "$("$bundled" --version)" != {shlex.quote(spec['cli_version'])} ]; then
    exec "$bundled" "$@"
fi
exec "$managed_dir/runtime/bin/codex" {shlex.join([arg for name in spec['features'] for arg in ('--enable', name)])} "$@"
'''
    launcher = f'''#!/bin/sh
set -eu
managed_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$managed_dir/enabled" ]; then
    echo "The managed runtime is disabled. Ask Astra Runtime Manager to enable it."
    exit 1
fi
processes=$(/bin/ps -axo comm=)
if printf '%s\\n' "$processes" | /usr/bin/awk -v app={shlex.quote(str(app) + '/Contents/')} 'index($0, app) == 1 {{ found=1 }} END {{ exit !found }}'; then
    echo "Quit Codex after active tasks finish, then run this launcher again."
    exit 1
fi
exec /usr/bin/open -a {shlex.quote(str(app))} --env "CODEX_CLI_PATH=$managed_dir/codex-patched"
'''
    for name, contents in [("codex-patched", wrapper), ("launch-patched.command", launcher)]:
        path = root / name
        path.write_text(contents)
        path.chmod(0o755)


def write_portable_launcher(root, specification):
    source = '''#!/usr/bin/env python3
"""Launch only this validated runtime; fall back when the original CLI changes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SPEC = json.loads(SPECIFICATION)
root = Path(__file__).resolve().parent
command = SPEC["original_command"]
if (root / "enabled").is_file() and (root / "receipt.json").is_file() and Path(SPEC["patched_command"][0]).is_file():
    try:
        with tempfile.TemporaryDirectory(prefix="astra-launch-check-") as temporary:
            env = dict(os.environ, CODEX_HOME=temporary)
            result = subprocess.run(command + ["--version"], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", env=env, timeout=15)
        if result.returncode == 0 and (result.stdout or result.stderr).strip() == SPEC["cli_version"]:
            command = SPEC["patched_command"] + [arg for feature in SPEC["features"] for arg in ("--enable", feature)]
    except (OSError, subprocess.SubprocessError):
        pass
arguments = command + sys.argv[1:]
if os.name == "nt":
    raise SystemExit(subprocess.call(arguments))
os.execv(arguments[0], arguments)
'''.replace('SPECIFICATION', repr(json.dumps(specification)))
    (root / "codex-patched.py").write_text(source, encoding="utf-8")


def install_package(root, package, app=None, origin="local_package", installation=None):
    installation = installation or resolve_installation(app)
    release = installation["release"]
    spec = release["spec"]
    if (root / "runtime").exists():
        raise ManagerError("A runtime is already present; inspect status or remove it before replacing it")
    hash_tree(package)  # Reject symlinks before copying or executing anything.
    metadata = json.loads((package / "codex-package.json").read_text())
    entrypoint = "bin/codex.exe" if "windows" in spec["tested_target"] else "bin/codex"
    if (metadata.get("target") != spec["tested_target"] or metadata.get("entrypoint") != entrypoint
            or metadata.get("variant") != "codex" or metadata.get("layoutVersion") != 1
            or metadata.get("version") != release["package_version"]):
        raise ManagerError("Package layout, version, or platform is not supported")
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=root) as temporary:
        candidate = Path(temporary) / "runtime"
        for relative in package_files(spec["tested_target"]):
            source = package / relative
            if not source.is_file():
                raise ManagerError(f"Package file missing: {relative}")
            destination = candidate / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        validation = root / "validation"
        validation.mkdir(exist_ok=True)
        for name in ("package_smoke.py", "app_server_smoke.py"):
            print(f"Validating: {name}", flush=True)
            run([sys.executable, RESOURCES / name, candidate, "--output", validation], timeout=180)
        checks = {}
        for name in ("package-smoke.json", "app-server-smoke.json"):
            checks[name] = json.loads((validation / name).read_text())
            if checks[name].get("passed") is not True:
                raise ManagerError("A package validation check did not pass")
        hashes = hash_tree(candidate)
        candidate.rename(root / "runtime")
    if installation["app"]:
        create_launchers(root, Path(installation["app"]), release)
    write_portable_launcher(root, {"original_command": [installation["cli"]],
                            "patched_command": [str(root / "runtime" / entrypoint)],
                            "cli_version": spec["cli_version"], "features": spec["features"]})
    write_json(root / "receipt.json", {"app": installation["app"], "cli": installation["cli"], "origin": origin,
               "target": spec["tested_target"], "validation_scope": "local_package_and_protocol_checks",
               "cli_version": spec["cli_version"], "release_id": release["id"],
               "source_commit": spec["commit"] if origin == "source_build" else None,
               "patch_sha256": spec["patch_sha256"] if origin == "source_build" else None,
               "files_sha256": hashes, "checks": checks,
               "validated_at": datetime.now(timezone.utc).isoformat()})
    return {"installed": True, "enabled_for_launcher": False,
            "next_step": ("Enable the launcher, then quit Codex and run launch-patched.command."
                          if installation["app"] else "Enable the launcher, then run Python with codex-patched.py and your CLI arguments.")}


def build_and_install(root, app=None, installation=None):
    installation = installation or resolve_installation(app)
    release = installation["release"]
    spec = release["spec"]
    if (root / "runtime").exists():
        raise ManagerError("A runtime is already present; inspect status before building another")
    if sys.version_info < (3, 11):
        raise ManagerError("Source builds require Python 3.11 or later; invoke this script with that Python")
    for command in ("git", "just", "cargo", "rustup"):
        if not shutil.which(command):
            raise ManagerError(f"Missing build prerequisite: {command}. See the plugin setup instructions.")
    run(["rustup", "run", release["rust_toolchain"], "rustc", "--version"])
    with tempfile.TemporaryDirectory(prefix="codex-astra-build-") as temporary:
        work = Path(temporary)
        source = work / "codex"
        package = work / "package"
        print("Fetching the pinned upstream release...", flush=True)
        run(["git", "clone", "--depth", "1", "--branch", spec["tag"], spec["upstream"], source])
        sys.path.insert(0, str(RESOURCES))
        from patch_guard import PatchError, process
        try:
            process(source, release["manifest_path"], apply=True)
        except PatchError as error:
            raise ManagerError(f"Source compatibility check failed: {error}") from error
        log = root / "build.log"
        print(f"Building the runtime; progress is saved in {log}", flush=True)
        env = os.environ.copy()
        env["RUSTUP_TOOLCHAIN"] = release["rust_toolchain"]
        env["PATH"] = str(Path(sys.executable).resolve().parent) + os.pathsep + env.get("PATH", "")
        with log.open("w") as output:
            arguments = [
                "just", "assemble-codex-package", "--target", spec["tested_target"],
                "--variant", "codex", "--cargo-profile", "release", "--package-version",
                release["package_version"], "--package-dir", str(package)]
            if installation["host"]:
                arguments += ["--code-mode-host-bin", installation["host"]]
            result = subprocess.run(arguments,
                cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ManagerError(f"Build failed; see {log}")
        return install_package(root, package, origin="source_build", installation=installation)


def enable(root):
    receipt = verify_installation(root)
    check_receipt_app(receipt)
    (root / "enabled").write_text("enabled for explicit launcher\n")
    return {"enabled_for_launcher": True, "restart_required": True,
            "launcher": str(root / ("launch-patched.command" if receipt.get("app") else "codex-patched.py")),
            "integration": "desktop" if receipt.get("app") else "standalone_cli"}


def disable(root):
    require_owner(root)
    (root / "enabled").unlink(missing_ok=True)
    return {"enabled_for_launcher": False, "next_step": "Quit any patched instance and open Codex normally."}


def launch(root):
    receipt = verify_installation(root)
    if not receipt.get("app"):
        raise ManagerError("Standalone CLI: run Python with the returned codex-patched.py path and your CLI arguments")
    app = Path(receipt["app"])
    check_receipt_app(receipt)
    if not (root / "enabled").is_file():
        raise ManagerError("Enable the runtime before launching it")
    commands = running_commands()
    if is_active(root, commands) or any(command.strip().startswith(str(app) + "/Contents/") for command in commands):
        raise ManagerError("Codex is running; finish active tasks and quit it before launching the patch")
    run(["open", "-a", app, "--env", f"CODEX_CLI_PATH={root / 'codex-patched'}"])
    return {"launch_requested": True, "note": "Check status after startup to confirm the actual runtime."}


def remove(root):
    if not root.exists():
        return {"removed": False, "note": "No managed runtime exists."}
    require_owner(root)
    if is_active(root, running_commands()):
        raise ManagerError("The managed runtime is running; quit that Codex instance before removal")
    allowed = {"owner.json", "receipt.json", "enabled", "runtime", "validation", "build.log",
               "codex-patched", "codex-patched.py", "launch-patched.command", ".operation-lock"}
    if any(path.name not in allowed or path.is_symlink() for path in root.iterdir()):
        raise ManagerError("Unexpected files exist in the managed directory; inspect and preserve them before removal")
    if (root / "runtime").exists() and (root / "receipt.json").is_file():
        receipt = json.loads((root / "receipt.json").read_text())
        if set(hash_tree(root / "runtime")) - set(receipt["files_sha256"]):
            raise ManagerError("Unexpected runtime files exist; preserve them before removal")
    shutil.rmtree(root)
    return {"removed": True, "note": "Open Codex normally. Plugin uninstallation is a separate action."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["doctor", "status", "setup", "install", "enable", "disable", "launch", "remove"])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--app", type=Path, help="Desktop app location; detected when exactly one is found")
    parser.add_argument("--cli", help="CLI executable for diagnostics or standalone runtime setup")
    parser.add_argument("--experimental", action="store_true", help="Build a source-checked target requiring local runtime validation")
    parser.add_argument("--target", help="Native Rust target; must match this OS/CPU (Linux GNU or musl)")
    parser.add_argument("--package", type=Path, help="Import a trusted local package instead of compiling source")
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    try:
        if args.action == "doctor":
            result = compatibility.doctor(args.cli)
        elif args.action == "status":
            result = status(root)
        elif args.action in ("remove", "disable") and not root.exists():
            result = {"installed": False}
        else:
            if args.action in ("setup", "install"):
                installation = resolve_installation(args.app, args.cli, experimental=args.experimental, target=args.target)
                claim_root(root)
            else:
                require_owner(root)
            with operation_lock(root):
                if args.action in ("setup", "install"):
                    if args.action == "setup" and (root / "receipt.json").is_file():
                        receipt = verify_installation(root)
                        original = receipt.get("cli") or str(Path(receipt["app"]) / "Contents/Resources/codex")
                        if Path(original).resolve() != Path(installation["cli"]).resolve():
                            raise ManagerError("Existing runtime belongs to a different CLI; inspect status first")
                        result = {"installed": True}
                    else:
                        result = (install_package(root, args.package.expanduser().resolve(strict=True), installation=installation)
                                  if args.package else build_and_install(root, installation=installation))
                    if args.action == "setup":
                        result.update(enable(root))
                else:
                    result = {"enable": enable, "disable": disable, "launch": launch, "remove": remove}[args.action](root)
        print(json.dumps(result, indent=2))
    except (ManagerError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Astra runtime manager: {error}\n")


if __name__ == "__main__":
    main()
