#!/usr/bin/env python3
"""Check the packaged desktop protocol without opening a model session."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import queue
import threading
import time



def main(package, output_dir):
    metadata = json.loads((package / "codex-package.json").read_text())
    assert metadata.get("entrypoint") in ("bin/codex", "bin/codex.exe"), "Unsupported package entrypoint"
    with tempfile.TemporaryDirectory(prefix="astra-app-server-smoke-") as temporary:
        home = Path(temporary)
        (home / "config.toml").write_text(
            'model = "gpt-6-astra"\nmodel_reasoning_effort = "xhigh"\n'
        )
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(home)
        with (output_dir / "app-server-smoke.stderr.log").open("w") as stderr:
            process = subprocess.Popen(
                [str(package / metadata["entrypoint"]), "--enable", "reasoning_effort_override",
                 "--enable", "event_driven_wait", "app-server"],
                cwd=home, env=environment, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=stderr, text=True,
            )
            replies = queue.Queue()

            def read_replies():
                for line in process.stdout:
                    replies.put(line)
                replies.put(None)

            reader = threading.Thread(target=read_replies, daemon=True)
            reader.start()

            def send(message):
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()

            def receive(identifier):
                deadline = time.monotonic() + 30
                while True:
                    line = replies.get(timeout=max(0, deadline - time.monotonic()))
                    if line is None:
                        raise AssertionError("App server closed before replying")
                    message = json.loads(line)
                    if message.get("id") == identifier:
                        assert "error" not in message, message
                        return message["result"]

            try:
                send({"id": 1, "method": "initialize", "params": {
                    "clientInfo": {"name": "astra_patch_validation", "version": "1.0.0"},
                    "capabilities": {"experimentalApi": True},
                }})
                initialized = receive(1)
                send({"method": "initialized", "params": {}})
                send({"id": 2, "method": "config/read", "params": {}})
                configuration = receive(2)["config"]
                features = {}
                cursor = None
                identifier = 3
                while True:
                    parameters = {"limit": 100}
                    if cursor:
                        parameters["cursor"] = cursor
                    send({"id": identifier, "method": "experimentalFeature/list", "params": parameters})
                    feature_response = receive(identifier)
                    features.update({item["name"]: item["enabled"] for item in feature_response["data"]})
                    cursor = feature_response.get("nextCursor")
                    if not cursor:
                        break
                    identifier += 1
                assert configuration["model"] == "gpt-6-astra", configuration.get("model")
                assert configuration["model_reasoning_effort"] == "xhigh", configuration.get("model_reasoning_effort")
                for name in ("reasoning_effort_override", "event_driven_wait"):
                    assert features.get(name) is True, (name, features.get(name))
                result = {"passed": True, "initialized": bool(initialized),
                          "model": configuration["model"], "effort": configuration["model_reasoning_effort"],
                          "enabled_features": ["reasoning_effort_override", "event_driven_wait"],
                          "model_requests": 0}
                (output_dir / "app-server-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result))
            finally:
                process.stdin.close()
                try:
                    code = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        code = process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        code = process.wait(timeout=5)
                reader.join(timeout=2)
                process.stdout.close()
                assert code == 0, "App server exited unsuccessfully"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Canonical Codex package directory")
    parser.add_argument("--output", type=Path, default=Path("validation-output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    main(args.package.resolve(strict=True), args.output.resolve())
