# Build and try the pinned runtime

This guide targets the initially tested environment: Apple Silicon macOS with Codex CLI `0.154.0-alpha.6.2`. Other operating systems need separate validation. Read `COMPATIBILITY.md` first: do not enable the cache feature with unsupported API modes or legacy remote compaction. Keep the installed desktop application intact and build into a separate directory.

## Prerequisites

- Git and Apple's command-line developer tools.
- Rust toolchain `1.95.0`, as pinned by the upstream `codex-rs/rust-toolchain.toml`.
- Python 3.11+ for the upstream package builder. The small scripts in this repository also work on Python 3.9.
- `just`; the initial build used 1.58.0.
- Network access and substantial free disk space for Rust build dependencies and artifacts. The first build can take many minutes.
- A matching installed Codex app, for the optional reuse of its Code Mode host in the command below.

For Rust test/format/schema work, the initial environment additionally used cargo-nextest 0.9.144, DotSlash 0.5.7, `uv`, rustfmt, and Clippy. Follow the pinned upstream `AGENTS.md` and package-builder documentation.

## Apply and build

First follow the README's clone/check/apply commands. From this toolkit repository, save its absolute path:

```sh
toolkit_root="$PWD"
codex_app="/Applications/ChatGPT.app"
"$codex_app/Contents/Resources/codex" --version
```

The last command must report exactly `codex-cli 0.154.0-alpha.6.2`. If the application is installed elsewhere, adjust `codex_app`. Stop if the version differs; the source patch and helper combination have not been validated for that version.

```sh
cd upstream
just assemble-codex-package \
  --target aarch64-apple-darwin \
  --variant codex \
  --cargo-profile release \
  --package-version 0.154.0-alpha.6.2+astra-cache-wait.1 \
  --package-dir "$toolkit_root/runtime" \
  --code-mode-host-bin "$codex_app/Contents/Resources/codex-code-mode-host"
cd "$toolkit_root"
```

This uses the upstream package builder. It resolves and verifies its V8 artifacts and package resources, including its patched zsh and ripgrep. Omitting the helper override lets upstream build the helper itself, but that alternative was not used for the initial package validation.

The release tag's Cargo manifests stamp local workspace packages with the release version while its lockfile contains local `0.0.0` entries. Cargo may normalize those entries during a build. Do not publish unrelated lockfile churn or silently update external dependencies. Keep the original lockfile to inspect and restore after build/test work if needed.

## Validate the package

From this toolkit repository:

```sh
python3 scripts/package_smoke.py runtime
python3 scripts/app_server_smoke.py runtime
```

Both must succeed before activation. They save local results under ignored `validation-output/`. They use temporary Codex homes; the model mock uses fake credentials and a loopback-only endpoint. These checks validate packaging and local runtime behavior, not a real model's billing or answer quality.

For source changes, run upstream's Rust checks too. From `upstream/codex-rs`, a focused nextest filter is:

```sh
just test -p codex-core -E 'test(reasoning_effort_override) | test(event_driven_wait) | test(code_mode_event_wait) | test(code_mode_wait) | test(session::reasoning_effort::tests)' --test-threads 2 --retries 0
```

Code Mode tests need a discoverable matching host binary; when testing only core, set `CARGO_BIN_EXE_codex_code_mode_host` to the absolute path of the matching host. Some upstream integration tests skip when a sandbox reports networking disabled: verify that tests actually execute, in an appropriately authorized test environment, instead of counting skipped tests as passes. Do not alter the source's sandbox checks.

See `VERIFICATION.md` for the broad-suite baseline failures and missing voice dependencies encountered during initial validation. Do not interpret the focused filter as a complete suite.

## Try it in the terminal

After validation, from the toolkit repository:

```sh
runtime/bin/codex --enable reasoning_effort_override --enable event_driven_wait
```

This reads your normal Codex configuration and authentication. It preserves your model/effort selection. Start with disposable tasks before using it for important work. No global configuration edits are needed to pass these two flags.

## Optional desktop activation

The initially inspected desktop app accepts a `CODEX_CLI_PATH` runtime override on launch. This is a version-specific integration, not a promise about every future desktop release.

After both smoke checks pass, create a local wrapper inside the ignored package directory:

```sh
cat > runtime/codex-patched <<'SH'
#!/bin/sh
set -eu
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bundled="${CODEX_ASTRA_APP:-/Applications/ChatGPT.app}/Contents/Resources/codex"
if [ ! -x "$package_dir/bin/codex" ] ||
   [ "$("$bundled" --version)" != 'codex-cli 0.154.0-alpha.6.2' ]; then
    exec "$bundled" "$@"
fi
exec "$package_dir/bin/codex" --enable reasoning_effort_override --enable event_driven_wait "$@"
SH
chmod +x runtime/codex-patched
```

Finish active tasks and **quit Codex**. Then launch the app with the explicit override:

```sh
open -a "$codex_app" \
  --env "CODEX_ASTRA_APP=$codex_app" \
  --env "CODEX_CLI_PATH=$toolkit_root/runtime/codex-patched"
```

The wrapper falls back to the bundled CLI when its version changes. Do not assume that opening another window in an already running app changes its runtime. Verify the actual launched runtime before starting a benchmark.

## Rollback

Close the patched CLI or quit the patched desktop instance. Open Codex normally without the override, or use your original CLI command. This guide does not replace the signed app, change shell aliases, install a login service, or edit global model settings. Use the explicit wrapper again when you want another patched desktop session.
