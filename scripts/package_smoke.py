#!/usr/bin/env python3
"""Exercise the packaged CLI and Code Mode host against a local mock server."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


REQUESTS = []
MARKER = "PACKAGE_HOST_OK"


def completed(response_id):
    return {"type": "response.completed", "response": {
        "id": response_id,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"models":[]}')

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        request = json.loads(body)
        REQUESTS.append(request)
        if len(REQUESTS) == 1:
            events = [{"type": "response.output_item.done", "item": {
                "type": "custom_tool_call", "call_id": "package-exec",
                "name": "exec", "input": f"text('{MARKER}');",
            }}, completed("package-first")]
        else:
            events = [{"type": "response.output_item.done", "item": {
                "type": "message", "role": "assistant", "id": "package-message",
                "content": [{"type": "output_text", "text": "Package check completed."}],
            }}, completed("package-final")]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for event in events:
            self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
        self.wfile.flush()


def main(package, output_dir):
    binary = package / "bin/codex"
    assert binary.is_file(), "Package must be built first"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    try:
        with tempfile.TemporaryDirectory(prefix="astra-package-smoke-") as temporary:
            directory = Path(temporary)
            home = directory / "codex-home"
            work = directory / "work"
            home.mkdir()
            work.mkdir()
            env = os.environ.copy()
            env.update({"CODEX_HOME": str(home), "OPENAI_API_KEY": "local-mock-only",
                        "HTTP_PROXY": address, "HTTPS_PROXY": address,
                        "ALL_PROXY": address, "NO_PROXY": "127.0.0.1,localhost"})
            for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
                env.pop(name, None)
            args = [str(binary), "--enable", "reasoning_effort_override",
                    "--enable", "event_driven_wait", "--enable", "code_mode",
                    "-c", 'model_provider="localmock"',
                    "-c", 'model_providers.localmock.name="OpenAI"',
                    "-c", f'model_providers.localmock.base_url="{address}/v1"',
                    "-c", 'model_providers.localmock.env_key="OPENAI_API_KEY"',
                    "-c", "model_providers.localmock.request_max_retries=0",
                    "-c", "model_providers.localmock.stream_max_retries=0",
                    "-c", 'model_reasoning_effort="xhigh"',
                    "exec", "--model", "gpt-6-astra", "--skip-git-repo-check",
                    "--json", "Run the local package validation."]
            result = subprocess.run(args, cwd=work, env=env, capture_output=True, text=True)
            (output_dir / "package-smoke.stdout.log").write_text(result.stdout)
            (output_dir / "package-smoke.stderr.log").write_text(result.stderr)
            assert result.returncode == 0, f"CLI failed: see package-smoke.stderr.log ({result.returncode})"
            assert len(REQUESTS) == 2, f"Expected two local requests, saw {len(REQUESTS)}"
            outputs = [item for item in REQUESTS[1].get("input", [])
                       if item.get("type") in ("custom_tool_call_output", "function_call_output")
                       and item.get("call_id") == "package-exec"]
            texts = []
            for item in outputs:
                output = item.get("output", [])
                if isinstance(output, str):
                    texts.extend(output.splitlines())
                else:
                    texts.extend(part.get("text", "") for part in output if isinstance(part, dict))
            assert MARKER in texts and any("Script completed" in text for text in texts), (
                "Code Mode did not produce the marker; see package-smoke logs"
            )
            assert REQUESTS[0].get("reasoning", {}).get("effort") == "xhigh"
            assert REQUESTS[0].get("model") == "gpt-6-astra"
            summary = {"passed": True, "local_requests": 2, "code_mode_output": MARKER,
                       "selected_model": "gpt-6-astra", "request_effort": "xhigh"}
            (output_dir / "package-smoke.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps(summary))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Canonical Codex package directory")
    parser.add_argument("--output", type=Path, default=Path("validation-output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    main(args.package.resolve(strict=True), args.output.resolve())
