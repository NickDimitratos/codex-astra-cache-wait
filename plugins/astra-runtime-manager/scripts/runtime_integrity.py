"""Integrity checks shared with, and embedded in, standalone runtime launchers."""

import hashlib
import json
from pathlib import Path

OWNER = {"owner": "astra-runtime-manager", "schema": 1}


class ManagerError(Exception):
    pass


def require_owner(root):
    if root.is_symlink():
        raise ManagerError("Refusing a symlink as the managed directory")
    marker = root / "owner.json"
    if marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != OWNER:
        raise ManagerError("This directory is not owned by the managed runtime")


def hash_tree(root):
    if root.is_symlink():
        raise ManagerError("Package root is a symlink")
    if not root.is_dir():
        raise ManagerError("Package directory is missing")
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


def verify_installation(root):
    require_owner(root)
    receipt_path = root / "receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ManagerError("No validated installation is recorded")
    receipt = json.loads(receipt_path.read_text())
    if not isinstance(receipt, dict) or not isinstance(receipt.get("files_sha256"), dict) or not receipt["files_sha256"]:
        raise ManagerError("Installation receipt has no valid file hashes")
    if hash_tree(root / "runtime") != receipt["files_sha256"]:
        raise ManagerError("Installed runtime checksum verification failed")
    return receipt
