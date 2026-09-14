import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/astra-runtime-manager"


class PluginBundleTests(unittest.TestCase):
    def test_standalone_resources_match_reviewed_sources(self):
        resources = PLUGIN / "resources"
        mapping = {
            "compatibility.json": "compatibility.json",
            "LICENSE": "LICENSE", "NOTICE": "NOTICE",
            "COMPATIBILITY.md": "docs/COMPATIBILITY.md",
            "COMMUNITY.md": "docs/COMMUNITY.md",
            "MEASUREMENTS.md": "docs/MEASUREMENTS.md",
            "RELEASES.md": "docs/RELEASES.md",
            "examples/synthetic-before.jsonl": "examples/synthetic-before.jsonl",
            "examples/synthetic-after.jsonl": "examples/synthetic-after.jsonl",
            "patch_guard.py": "scripts/patch_guard.py",
            "package_smoke.py": "scripts/package_smoke.py",
            "app_server_smoke.py": "scripts/app_server_smoke.py",
            "patches/astra-cache-and-idle-wait.patch": "patches/astra-cache-and-idle-wait.patch",
        }
        for bundled, original in mapping.items():
            with self.subTest(resource=bundled):
                self.assertEqual((resources / bundled).read_bytes(), (ROOT / original).read_bytes())

    def test_bundled_patch_checksum_matches_manifest(self):
        resources = PLUGIN / "resources"
        spec = json.loads((resources / "compatibility.json").read_text())
        self.assertEqual(hashlib.sha256((resources / spec["patch"]).read_bytes()).hexdigest(),
                         spec["patch_sha256"])

    def test_checkout_preserves_patch_hash_with_crlf_enabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            checkout = Path(temporary) / "checkout"
            root.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args],
                                      capture_output=True, text=True, check=True)
            git("init", "-q")
            (root / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
            paths = ["patches/astra-cache-and-idle-wait.patch",
                     "plugins/astra-runtime-manager/resources/patches/astra-cache-and-idle-wait.patch"]
            for name in paths:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            git("add", ".")
            git("-c", "core.autocrlf=true", "-c", "core.eol=crlf", "checkout-index",
                "--all", "--prefix=" + checkout.as_posix() + "/")
            for name in paths:
                self.assertEqual((checkout / name).read_bytes(), (ROOT / name).read_bytes())

    def test_marketplace_resolves_self_contained_plugin(self):
        catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(catalog["name"], "astra-runtime")
        self.assertEqual(len(catalog["plugins"]), 1)
        entry = catalog["plugins"][0]
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual((ROOT / entry["source"]["path"]).resolve(), PLUGIN.resolve())
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], entry["name"])
        skills = PLUGIN / manifest["skills"]
        self.assertTrue((skills / "astra-runtime-manager/SKILL.md").is_file())
        self.assertTrue((PLUGIN / "scripts/manage_runtime.py").is_file())
        for unsupported in ("hooks", "mcpServers", "apps"):
            self.assertNotIn(unsupported, manifest)


if __name__ == "__main__":
    unittest.main()
