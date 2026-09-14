#!/usr/bin/env python3
"""Check or apply the pinned patch to a clean, matching Codex source checkout."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


class PatchError(Exception):
    pass


def git(source, *arguments):
    result = subprocess.run(["git", "-C", str(source), *arguments],
                            capture_output=True, text=True)
    if result.returncode:
        raise PatchError(result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def process(source, manifest, *, apply=False):
    source = Path(source).resolve(strict=True)
    manifest = Path(manifest).resolve(strict=True)
    specification = json.loads(manifest.read_text())
    patch = (manifest.parent / specification["patch"]).resolve(strict=True)
    if not patch.is_relative_to(manifest.parent):
        raise PatchError("Patch must stay inside this repository")
    if hashlib.sha256(patch.read_bytes()).hexdigest() != specification["patch_sha256"]:
        raise PatchError("Patch checksum differs from compatibility.json")
    repository = Path(git(source, "rev-parse", "--show-toplevel")).resolve()
    if repository != source:
        raise PatchError("Supply the Codex repository root, not a subdirectory")
    if git(source, "rev-parse", "HEAD") != specification["commit"]:
        raise PatchError("Source commit does not match compatibility.json; use the pinned release")
    if git(source, "status", "--porcelain", "--untracked-files=all"):
        raise PatchError("A clean checkout is required; preserve existing work in a separate checkout")
    git(source, "apply", "--check", str(patch))
    if apply:
        git(source, "apply", str(patch))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "apply"])
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        process(args.source, Path(__file__).resolve().parents[1] / "compatibility.json",
                apply=args.action == "apply")
    except (PatchError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Cannot {args.action} patch: {error}\n")
    print("Patch applied." if args.action == "apply" else "Matching clean source; patch can be applied.")


if __name__ == "__main__":
    main()
