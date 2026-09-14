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

RESOURCES = Path(__file__).resolve().parents[1] / "resources"
SPEC = json.loads((RESOURCES / "compatibility.json").read_text())
OWNER = {"owner": "astra-runtime-manager", "schema": 1}
PACKAGE_FILES = ("codex-package.json", "bin/codex", "bin/codex-code-mode-host",
                 "codex-path/rg", "codex-resources/zsh/bin/zsh")
DEFAULT_ROOT = Path.home() / ".local/share/codex-astra-cache-wait"


class ManagerError(Exception):
    pass


def run(arguments, **kwargs):
    result = subprocess.run([str(value) for value in arguments], capture_output=True,
                            text=True, **kwargs)
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
    return run(["ps", "-axo", "comm="]).splitlines()


def is_active(root, commands):
    prefixes = (str(root.absolute()) + os.sep, str(root.resolve()) + os.sep)
    return any(command.strip().startswith(prefixes) for command in commands)


def check_app(app):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ManagerError("This release supports Apple Silicon macOS only")
    binary = app / "Contents/Resources/codex"
    host = app / "Contents/Resources/codex-code-mode-host"
    if not binary.is_file() or not host.is_file():
        raise ManagerError("The selected app must contain Codex and its Code Mode host")
    with tempfile.TemporaryDirectory(prefix="astra-version-") as temporary:
        env = os.environ.copy()
        env["CODEX_HOME"] = temporary
        version = run([binary, "--version"], env=env)
    if version != SPEC["cli_version"]:
        raise ManagerError(f"Unsupported Codex version: {version}; expected {SPEC['cli_version']}")
    return version


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
              "supported_platform": platform.system() == "Darwin" and platform.machine() == "arm64",
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
                   "launcher": str(root / "launch-patched.command"), "origin": receipt["origin"]})
    try:
        result["running"] = is_active(root, running_commands())
    except ManagerError:
        result["running"] = None
        result["process_status"] = "unknown: process inspection was unavailable"
    try:
        check_app(Path(receipt["app"]))
        result["app_compatible"] = True
    except ManagerError as error:
        result["app_compatible"] = False
        result["compatibility_note"] = str(error)
    return result


def create_launchers(root, app):
    bundled = shlex.quote(str(app / "Contents/Resources/codex"))
    wrapper = f'''#!/bin/sh
set -eu
managed_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bundled={bundled}
if [ ! -f "$managed_dir/enabled" ] || [ ! -f "$managed_dir/receipt.json" ] ||
   [ ! -x "$managed_dir/runtime/bin/codex" ] ||
   [ "$("$bundled" --version)" != {shlex.quote(SPEC['cli_version'])} ]; then
    exec "$bundled" "$@"
fi
exec "$managed_dir/runtime/bin/codex" --enable reasoning_effort_override --enable event_driven_wait "$@"
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


def install_package(root, package, app, origin="local_package"):
    check_app(app)
    if (root / "runtime").exists():
        raise ManagerError("A runtime is already present; inspect status or remove it before replacing it")
    hash_tree(package)  # Reject symlinks before copying or executing anything.
    metadata = json.loads((package / "codex-package.json").read_text())
    if (metadata.get("target") != SPEC["tested_target"] or metadata.get("entrypoint") != "bin/codex"
            or metadata.get("variant") != "codex" or metadata.get("layoutVersion") != 1
            or metadata.get("version") != "0.154.0-alpha.6.2+astra-cache-wait.1"):
        raise ManagerError("Package layout, version, or platform is not supported")
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=root) as temporary:
        candidate = Path(temporary) / "runtime"
        for relative in PACKAGE_FILES:
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
            run([sys.executable, RESOURCES / name, candidate, "--output", validation])
        checks = {}
        for name in ("package-smoke.json", "app-server-smoke.json"):
            checks[name] = json.loads((validation / name).read_text())
            if checks[name].get("passed") is not True:
                raise ManagerError("A package validation check did not pass")
        hashes = hash_tree(candidate)
        candidate.rename(root / "runtime")
    create_launchers(root, app)
    write_json(root / "receipt.json", {"app": str(app), "origin": origin,
               "source_commit": SPEC["commit"] if origin == "source_build" else None,
               "patch_sha256": SPEC["patch_sha256"] if origin == "source_build" else None,
               "files_sha256": hashes, "checks": checks,
               "validated_at": datetime.now(timezone.utc).isoformat()})
    return {"installed": True, "enabled_for_launcher": False,
            "next_step": "Enable the launcher, then quit Codex and run launch-patched.command."}


def build_and_install(root, app):
    check_app(app)
    if (root / "runtime").exists():
        raise ManagerError("A runtime is already present; inspect status before building another")
    if sys.version_info < (3, 11):
        raise ManagerError("Source builds require Python 3.11 or later; invoke this script with that Python")
    for command in ("git", "just", "cargo", "rustup"):
        if not shutil.which(command):
            raise ManagerError(f"Missing build prerequisite: {command}. See the plugin setup instructions.")
    run(["rustup", "run", "1.95.0", "rustc", "--version"])
    with tempfile.TemporaryDirectory(prefix="codex-astra-build-") as temporary:
        work = Path(temporary)
        source = work / "codex"
        package = work / "package"
        print("Fetching the pinned upstream release...", flush=True)
        run(["git", "clone", "--depth", "1", "--branch", SPEC["tag"], SPEC["upstream"], source])
        sys.path.insert(0, str(RESOURCES))
        from patch_guard import PatchError, process
        try:
            process(source, RESOURCES / "compatibility.json", apply=True)
        except PatchError as error:
            raise ManagerError(f"Source compatibility check failed: {error}") from error
        log = root / "build.log"
        print(f"Building the runtime; progress is saved in {log}", flush=True)
        env = os.environ.copy()
        env["RUSTUP_TOOLCHAIN"] = "1.95.0"
        env["PATH"] = str(Path(sys.executable).resolve().parent) + os.pathsep + env.get("PATH", "")
        with log.open("w") as output:
            result = subprocess.run([
                "just", "assemble-codex-package", "--target", SPEC["tested_target"],
                "--variant", "codex", "--cargo-profile", "release", "--package-version",
                "0.154.0-alpha.6.2+astra-cache-wait.1", "--package-dir", str(package),
                "--code-mode-host-bin", str(app / "Contents/Resources/codex-code-mode-host")],
                cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ManagerError(f"Build failed; see {log}")
        return install_package(root, package, app, origin="source_build")


def enable(root):
    receipt = verify_installation(root)
    check_app(Path(receipt["app"]))
    (root / "enabled").write_text("enabled for explicit launcher\n")
    return {"enabled_for_launcher": True, "restart_required": True,
            "launcher": str(root / "launch-patched.command")}


def disable(root):
    require_owner(root)
    (root / "enabled").unlink(missing_ok=True)
    return {"enabled_for_launcher": False, "next_step": "Quit any patched instance and open Codex normally."}


def launch(root):
    receipt = verify_installation(root)
    app = Path(receipt["app"])
    check_app(app)
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
               "codex-patched", "launch-patched.command", ".operation-lock"}
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
    parser.add_argument("action", choices=["status", "install", "enable", "disable", "launch", "remove"])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--app", type=Path, default=Path("/Applications/ChatGPT.app"))
    parser.add_argument("--package", type=Path, help="Import a trusted local package instead of compiling source")
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    try:
        if args.action == "status":
            result = status(root)
        elif args.action in ("remove", "disable") and not root.exists():
            result = {"installed": False}
        else:
            if args.action == "install":
                claim_root(root)
            else:
                require_owner(root)
            with operation_lock(root):
                if args.action == "install":
                    app = args.app.expanduser().resolve(strict=True)
                    result = (install_package(root, args.package.expanduser().resolve(strict=True), app)
                              if args.package else build_and_install(root, app))
                else:
                    result = {"enable": enable, "disable": disable, "launch": launch, "remove": remove}[args.action](root)
        print(json.dumps(result, indent=2))
    except (ManagerError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Astra runtime manager: {error}\n")


if __name__ == "__main__":
    main()
