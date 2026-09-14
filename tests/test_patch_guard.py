import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("patch_guard", ROOT / "scripts/patch_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PatchGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source with spaces"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Patch Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.source / "example.txt").write_text("before\n")
        self.git("add", "example.txt")
        self.git("commit", "-qm", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()
        (self.source / "example.txt").write_text("after\n")
        self.patch = self.root / "change.patch"
        self.patch.write_text(self.git("diff", "--no-ext-diff"))
        (self.source / "example.txt").write_text("before\n")
        self.manifest = self.root / "compatibility.json"
        self.manifest.write_text(json.dumps({
            "commit": self.commit, "patch": "change.patch",
            "patch_sha256": hashlib.sha256(self.patch.read_bytes()).hexdigest(),
        }))

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.source), *arguments],
                              capture_output=True, text=True, check=True).stdout

    def test_check_does_not_modify_source(self):
        guard.process(self.source, self.manifest, apply=False)
        self.assertEqual((self.source / "example.txt").read_text(), "before\n")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_apply_changes_only_expected_file(self):
        guard.process(self.source, self.manifest, apply=True)
        self.assertEqual((self.source / "example.txt").read_text(), "after\n")
        self.assertEqual(self.git("diff", "--name-only").strip(), "example.txt")

    def test_refuses_wrong_revision(self):
        self.git("commit", "--allow-empty", "-qm", "different revision")
        with self.assertRaisesRegex(guard.PatchError, "commit"):
            guard.process(self.source, self.manifest, apply=True)
        self.assertEqual((self.source / "example.txt").read_text(), "before\n")

    def test_refuses_uncommitted_work(self):
        (self.source / "example.txt").write_text("user work\n")
        with self.assertRaisesRegex(guard.PatchError, "clean"):
            guard.process(self.source, self.manifest, apply=True)
        self.assertEqual((self.source / "example.txt").read_text(), "user work\n")

    def test_refuses_untracked_files(self):
        (self.source / "notes.txt").write_text("keep this\n")
        with self.assertRaisesRegex(guard.PatchError, "clean"):
            guard.process(self.source, self.manifest, apply=True)
        self.assertEqual((self.source / "notes.txt").read_text(), "keep this\n")

    def test_refuses_modified_patch(self):
        self.patch.write_text(self.patch.read_text() + "unexpected bytes\n")
        with self.assertRaisesRegex(guard.PatchError, "checksum"):
            guard.process(self.source, self.manifest, apply=True)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_refuses_subdirectory(self):
        directory = self.source / "nested"
        directory.mkdir()
        with self.assertRaisesRegex(guard.PatchError, "root"):
            guard.process(directory, self.manifest, apply=True)

    def test_second_apply_preserves_existing_patch(self):
        guard.process(self.source, self.manifest, apply=True)
        with self.assertRaisesRegex(guard.PatchError, "clean"):
            guard.process(self.source, self.manifest, apply=True)
        self.assertEqual((self.source / "example.txt").read_text(), "after\n")


if __name__ == "__main__":
    unittest.main()
