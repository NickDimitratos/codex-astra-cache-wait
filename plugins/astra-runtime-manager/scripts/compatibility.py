"""Read-only CLI discovery and exact, extensible runtime release selection."""

import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

RESOURCES = Path(__file__).resolve().parents[1] / "resources"


def catalog(resources=RESOURCES):
    data = json.loads((resources / "runtime-releases.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported runtime catalog schema")
    releases, identities = [], set()
    for entry in data["releases"]:
        manifest = (resources / entry["manifest"]).resolve()
        if not manifest.is_relative_to(resources.resolve()):
            raise ValueError("Release manifest must stay inside plugin resources")
        spec = json.loads(manifest.read_text(encoding="utf-8"))
        identity = (spec["cli_version"], entry["system"], entry["machine"])
        if identity in identities:
            raise ValueError("Duplicate runtime compatibility entry")
        identities.add(identity)
        releases.append(dict(entry, spec=spec, manifest_path=manifest))
    return releases


def select_release(version, system=None, machine=None, resources=RESOURCES):
    system = system or platform.system()
    machine = machine or platform.machine()
    return next((item for item in catalog(resources)
                 if item["spec"]["cli_version"] == version
                 and item["system"] == system and item["machine"] == machine), None)


def app_candidates():
    if platform.system() != "Darwin":
        return []
    return [parent / name for parent in (Path("/Applications"), Path.home() / "Applications")
            for name in ("ChatGPT.app", "Codex.app")
            if (parent / name / "Contents/Resources/codex").is_file()]


def discover_app(explicit=None):
    if explicit is not None:
        return Path(explicit).expanduser().resolve(strict=True)
    apps = app_candidates()
    if len(apps) != 1:
        raise ValueError("Select the desktop installation with --app /path/to/App.app; "
                         "no unique supported app location was found")
    return apps[0].resolve()


def probe(binary, args):
    # A separate home prevents normal config/plugin initialization during help probes.
    with tempfile.TemporaryDirectory(prefix="astra-cli-check-") as temporary:
        env = os.environ.copy()
        env["CODEX_HOME"] = temporary
        result = subprocess.run([str(binary), *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=15, env=env)
        if result.returncode:
            raise ValueError("CLI probe failed")
        return result.stdout.strip()


def inspect_cli(binary):
    result = {"executable": str(binary), "version": None, "native_plugins": None,
              "exec_json": None, "runtime_patch_available": False}
    try:
        version = probe(binary, ["--version"])
        if not re.fullmatch(r"codex-cli \S+", version):
            raise ValueError("Unrecognized CLI version response")
        result["version"] = version
        release = select_release(version)
        result["runtime_patch_available"] = release is not None
        result["release_id"] = release["id"] if release else None
        help_text = probe(binary, ["--help"])
        result["native_plugins"] = bool(re.search(r"(?m)^\s+plugin\s", help_text))
        if re.search(r"(?m)^\s+exec\s", help_text):
            result["exec_json"] = "--json" in probe(binary, ["exec", "--help"])
        else:
            result["exec_json"] = False
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["probe_note"] = "Some capabilities could not be read; no changes were made."
    result["next_step"] = ("Use setup with the matching desktop app, then restart through its launcher."
                           if result["runtime_patch_available"] else
                           "Use usage reports; runtime activation requires a tested release entry.")
    return result


def doctor(cli=None):
    if cli:
        binary = shutil.which(str(cli)) or str(Path(cli).expanduser())
        binaries = [Path(binary)]
    else:
        binaries = [Path(value) for value in [shutil.which("codex")] if value]
        binaries += [app / "Contents/Resources/codex" for app in app_candidates()]
    unique = list(dict.fromkeys(str(path.absolute()) for path in binaries))
    return {"schema_version": 1, "platform": platform.system(), "machine": platform.machine(),
            "installations": [inspect_cli(Path(path)) for path in unique],
            "usage_reports": "Available independently of runtime patch support; requires a recognized JSONL format.",
            "activation_performed": False,
            "universal_runtime_compatibility": False}
