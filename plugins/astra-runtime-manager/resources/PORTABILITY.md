# CLI versions, CPUs, and standalone setup

Version 0.3 adds standalone CLI setup and native target adapters for x86-64 and ARM64 on macOS, Linux, and Windows. A desktop app is no longer required for standalone setup. Local reporting remains independent of runtime patch availability.

**One source patch cannot safely cover every Codex release or every CPU.** The installer distinguishes a previously validated path from an experimental build candidate. It never downgrades your CLI or treats a successful patch-application check as a runtime test.

## Platform coverage

| Capability | macOS x86-64 / ARM64 | Linux x86-64 / ARM64 | Windows x86-64 / ARM64 |
| --- | --- | --- | --- |
| CLI capability checks / supported JSONL reports | Available | Available | Available |
| Standalone Python launcher | Available | Available | Available |
| Source build/package adapter | Available | GNU and musl targets | MSVC targets and sandbox helpers |
| Desktop integration | Explicit Mac launcher | Not provided | Not provided |
| All runtime binaries certified by this project | No | No | No |

The eight target adapters are:

- `x86_64-apple-darwin` and `aarch64-apple-darwin`.
- `x86_64-unknown-linux-gnu` and `aarch64-unknown-linux-gnu`.
- `x86_64-unknown-linux-musl` and `aarch64-unknown-linux-musl`.
- `x86_64-pc-windows-msvc` and `aarch64-pc-windows-msvc`.

CPU spellings such as AMD64, x64, x86_64, arm64, and aarch64 are normalized. Selection follows the running Python process architecture; a Python under emulation selects that architecture. 32-bit x86/ARM, RISC-V, and other unsupported targets are not advertised as buildable.

Layouts follow the [official package target definitions](https://github.com/openai/codex/blob/b5bffd3ec4db487e7e3dec59663875b0ef7b72ca/scripts/codex_package/targets.py). The installer preserves Linux bwrap and Windows sandbox helpers. Local execution checks must pass on the user's machine before enabling a package.

## CLI release evidence

Source checks performed on 2026-09-14:

| Release | Observed result | Installer behavior |
| --- | --- | --- |
| `0.153.4` | Required effort-override source files are absent | Diagnostics/reports; a separate patch port is needed |
| `0.154.0-alpha.6.2` | Original patch and Apple Silicon package were validated | Existing Apple Silicon path; other targets require experimental setup/local validation |
| `0.154.0` | Exact patch applies cleanly to stable source | Experimental build candidate; no completed Rust/runtime validation claimed for this release |
| `0.155.0-alpha.4` | Upstream contains request-effort pinning with compaction handling | Report upstream evidence; refuse the older patch |
| Other releases/custom builds | No applicable source evidence in the catalog | Probe capabilities; do not force a patch |

The newer implementation is in [upstream reasoning_effort.rs](https://github.com/openai/codex/blob/66eab8ece44141ff92707868269e1d53b40c4ac5/codex-rs/core/src/session/reasoning_effort.rs). Its reasoning_effort_override flag is [under development and disabled by default](https://github.com/openai/codex/blob/66eab8ece44141ff92707868269e1d53b40c4ac5/codex-rs/features/src/lib.rs). Finding that code does not establish live savings or this project's event-driven wait behavior. This plugin does not silently enable the upstream feature or upgrade your CLI.

## Standalone setup

Install the plugin as described in [COMMUNITY.md](COMMUNITY.md). In a new Codex task, paste:

> Use Astra Runtime Manager to check my CLI version, CPU, native target, and runtime paths. Explain whether this is a validated path, an experimental build candidate, or unsupported source.

If a candidate is listed and you want to try it:

> Set up the experimental standalone runtime for my selected CLI. Validate it locally, keep my sessions running, and give me the Python launcher command. Report failed checks.

From a repository clone:

```sh
python3 plugins/astra-runtime-manager/scripts/manage_runtime.py doctor --cli "/absolute/path/to/codex"
python3 plugins/astra-runtime-manager/scripts/manage_runtime.py setup --cli "/absolute/path/to/codex" --experimental
```

On Windows use your Python 3.11+ command and actual executable path, for example in PowerShell:

```powershell
python plugins/astra-runtime-manager/scripts/manage_runtime.py doctor --cli "C:\Tools\Codex\codex.exe"
python plugins/astra-runtime-manager/scripts/manage_runtime.py setup --cli "C:\Tools\Codex\codex.exe" --experimental
```

These paths are examples. On Windows prefer the native codex.exe over a package-manager .cmd/PowerShell shim for runtime setup. Capability detection can inspect supported shims. Use `--app` for macOS desktop setup; `--app` and `--cli` are mutually exclusive during setup.

Builds require Python 3.11+, Git, just, Rustup/the catalog's toolchain, a native compiler/linker, network access, and substantial disk space. macOS needs Apple's command-line tools. Windows needs MSVC C++ build tools and the Windows SDK. Linux needs the upstream native development dependencies and sandbox build support. GNU and musl toolchains are not interchangeable. Read build.log if compilation fails; a failed build is not installed or enabled.

The Linux target defaults to detected libc. `--target` can select GNU or musl for the same OS/CPU when the required toolchain exists. It cannot select another CPU/OS. Unknown releases are rejected even with `--experimental`.

## Launch, verify, and undo

Setup returns codex-patched.py for standalone installations. Run that exact path with Python and your normal Codex arguments:

```sh
python3 "$HOME/.local/share/codex-astra-cache-wait/codex-patched.py"
```

PowerShell with the default directory:

```powershell
python "$HOME/.local/share/codex-astra-cache-wait/codex-patched.py"
```

The Python launcher forwards arguments without a shell and preserves model/effort selection. After starting an interactive session, check `manage_runtime.py status` in another terminal or task. `running: true` means a managed executable was observed; null means inspection failed. A short --version command exits quickly and will normally be inactive by the time status is checked.

Disable makes the next launcher invocation use the original CLI. The launcher also falls back if the original CLI version changes. Close active patched CLI sessions before removal. A standalone setup does not change a desktop app's runtime.

For usage comparison, replace the after-run command in [MEASUREMENTS.md](MEASUREMENTS.md) with `python3 /actual/managed/path/codex-patched.py exec --json "Your agreed benchmark task"`. Verify enablement and the matching original CLI first; a fallback run is not a patched benchmark.

## Validation scope

Toolkit CI tests Python behavior on native x86-64 and ARM64 runners for all three operating systems, including argument forwarding and process inspection. It checks patch application for both cataloged sources. Toolkit tests are **not** builds or live model tests of the Rust runtime.

The real standalone lifecycle passed locally on Apple Silicon with the existing validated 0.154.0-alpha.6.2 package: import, local mock checks, enable, observed process, disable/fallback, and removal. No live model request was made. Other native builds require local validation and remain experimental. No cross-platform savings percentage is established.
