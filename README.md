# Astra Runtime Manager for the Codex community

Check CLI compatibility, measure token usage, and manage a separate experimental Astra runtime. **OpenCodex is optional.** Diagnostics and reporting do not require a custom runtime, API key, remote service, or model probe.

**Installing the plugin does not activate the runtime patch.** The source patch currently targets Codex CLI `0.154.0-alpha.6.2`; it addresses cache reuse when reasoning effort changes and empty waits that can trigger another model request.

## Community compatibility

| Capability | Supported scope |
| --- | --- |
| CLI detection | Version-independent help/version probes; unknown capabilities are explicit |
| Native CLI usage reports | Recognized `codex exec --json` layout; cumulative thread totals counted once |
| OpenCodex reports | Optional request-level usage JSONL, with request deduplication |
| Plugin installation | Releases with native plugin support; older CLIs can use the standalone Python tools |
| Runtime activation | Exact tested version/platform pairs in the release catalog |
| Current runtime entry | `0.154.0-alpha.6.2`, Apple Silicon macOS, matching desktop app |
| Automatically patch every past/future release | **Not supported**; source changes need release-specific validation |

Start with the [community setup guide](docs/COMMUNITY.md), [compatibility evidence](docs/RELEASES.md), and [measurement guide](docs/MEASUREMENTS.md). Unknown releases keep their original runtime. The tool does not downgrade a CLI or force an old patch onto it.

**Status: locally tested; live token savings have not been established.** This is an independent community experiment. It is not an official OpenAI or OpenCodex release, a universal installer, or a demonstrated fix for account allowance accounting.

## What changes

- **Stable reasoning configuration:** on the supported Astra path, preserve the request-level reasoning effort while trusted, appended configuration updates select the current effort. The selected effort is preserved, including XHigh.
- **Wait for useful activity:** the opt-in `event_driven_wait` feature keeps empty waits inside the runtime when no explicit deadline was supplied. Explicit timeouts retain their existing behavior. Code Mode can take up to ten seconds to notice new activity.
- **Keep compatibility checks:** the cache change is gated by the existing feature and provider/transport checks and the exact `gpt-6-astra` model identifier. It is not enabled for every model or provider.

The cache approach follows OpenAI's guidance to keep request-level effort stable when appending configuration updates. See [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) and [reasoning updates and compatibility](https://developers.openai.com/api/docs/guides/reasoning#change-reasoning-mid-conversation).

## Who should try the runtime patch

Developers who can build and test a custom Codex runtime and are using the **exact pinned release**. Start with disposable tasks and compare task quality as well as token usage.

| Component | Current evidence |
| --- | --- |
| Upstream tag | `rust-v0.154.0-alpha.6.2` |
| Commit | `b5bffd3ec4db487e7e3dec59663875b0ef7b72ca` |
| Built and tested platform | macOS, Apple Silicon (`aarch64-apple-darwin`) |
| Cache model | `gpt-6-astra`, standard single-agent API mode, subject to runtime gates |
| Windows, Linux, Intel macOS | Not runtime-validated by this project |
| Other Codex releases | Not supported by this patch manifest |
| Real workload savings | Not yet measured in a controlled comparison |

Read the [API and compaction limits](docs/COMPATIBILITY.md) before enabling the cache feature. In particular, the legacy remote compaction path is not supported with configuration updates. The included guard checks source compatibility; it does not certify every runtime configuration.

OpenCodex is not required to apply this Codex source patch. OpenCodex interception settings, routing, global instructions, personal logs, and account settings are outside this repository.

## Install the Codex plugin from GitHub

The repository includes **Astra Runtime Manager**, a Codex skill plugin that manages a separate patched runtime. With a recent Codex CLI:

```sh
codex plugin marketplace add NickDimitratos/codex-astra-cache-wait
codex plugin add astra-runtime-manager@astra-runtime
```

If an older CLI or OpenCodex shim is first on your PATH, use the compatible desktop app's bundled CLI for both commands, for example `/Applications/ChatGPT.app/Contents/Resources/codex`.

Start a **new Codex task/session** and ask “Use Astra Runtime Manager to check my CLI compatibility.” This follows the [official plugin workflow](https://learn.chatgpt.com/docs/plugins). The diagnostic checks PATH and common app locations, or an explicit `--cli` path. From a clone, run `python3 plugins/astra-runtime-manager/scripts/manage_runtime.py doctor`. On Windows, use `python` if that is your Python 3.9+ command.

To activate a supported runtime, ask “Set up and enable the Astra runtime, validate it, and give me the launcher. Keep my current tasks running.” The `setup` command builds or imports a package, validates it, and enables its launcher. Finish tasks, quit Codex, launch through the returned `launch-patched.command`, then verify **`running: true`**. `installed` and `enabled_for_launcher` do not prove activation.

Runtime setup requires the exact supported app version, Apple Silicon macOS, Python 3.11+, Git, just, Rustup/Rust 1.95.0, Apple's command-line tools, network access, and substantial build disk space. It validates the package, keeps it under `~/.local/share/codex-astra-cache-wait`, and supplies an explicit launcher. Finish active tasks and quit Codex before using that launcher.

To update this GitHub installation, run `codex plugin marketplace upgrade astra-runtime`, then `codex plugin add astra-runtime-manager@astra-runtime`, and start a new task/session. Updating the plugin does not silently replace a separately installed runtime.

To undo setup, ask “Restore normal Codex and remove the managed runtime.” Remove the managed runtime **before** uninstalling the plugin. Codex's plugin toggle and Uninstall button manage the plugin bundle; they do not undo an external runtime installation. Read the [plugin guide](plugins/astra-runtime-manager/README.md) for its status, enable, disable, and removal controls.

## Apply the source patch manually

Python 3.9+ and Git are sufficient to check/apply the patch. Building the runtime needs additional tools described in [BUILD.md](docs/BUILD.md).

From this repository's root:

```sh
git clone --depth 1 --branch rust-v0.154.0-alpha.6.2 https://github.com/openai/codex.git upstream
python3 scripts/patch_guard.py check upstream
python3 scripts/patch_guard.py apply upstream
```

The guard checks the patch checksum, exact upstream commit, repository root, and clean working tree. It refuses to overwrite existing work or apply the patch twice. It changes source files only: it does not install a runtime or modify the desktop app.

Read the [build, validation, activation, and rollback instructions](docs/BUILD.md) before running a patched runtime. Enable `reasoning_effort_override` and `event_driven_wait` only in the patched runtime. Setting these flags in an unrelated release does not install this fix.

## Evidence and limits

The existing verification covered stable prefixes, reasoning changes, trusted history, resume/fork, unsupported configurations, agent activity, and Code Mode waits. The broader suite was not completely green. See the exact [verification record](docs/VERIFICATION.md).

The GitHub Actions workflow checks the Python toolkit on Linux, macOS, and Windows, plus patch application on the exact pinned source. It does **not** build the Rust runtime or claim cross-platform runtime support.

Reproduce the reporting arithmetic without model calls using `examples/synthetic-before.jsonl` and `synthetic-after.jsonl`; the commands and numeric example are in [MEASUREMENTS.md](docs/MEASUREMENTS.md). These are fabricated examples, not measured savings. Reports export aggregates with explicit missing-data coverage. Observed changes and account allowance savings remain separate.

For useful before/after results, follow [BENCHMARKING.md](docs/BENCHMARKING.md). There is no fixed savings percentage: an unchanged-effort workload with no empty waits may see little or no benefit. Cached tokens, fresh tokens, reasoning tokens, and account allowance are different measurements.

## Contributing

Contributions are useful for newer release compatibility, runtime testing on other operating systems, comparable workload measurements, and upstream review. See [CONTRIBUTING.md](CONTRIBUTING.md). Keep raw conversations, authentication data, and identifying account information out of public issues.

The patch and toolkit are distributed under Apache-2.0; upstream attribution is retained in [LICENSE](LICENSE) and [NOTICE](NOTICE). The repository contains source and documentation, not desktop application binaries.
