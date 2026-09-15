# User guide: install, use, measure, and uninstall

Astra Runtime Manager is a community plugin for checking Codex compatibility, reading local token-usage logs, and managing an optional experimental runtime. A runtime is the program underneath Codex that sends model requests and handles tools.

**Installing the plugin alone does not activate the patch or reduce token usage.** Trying the runtime changes requires a supported installation, separate setup, and a restart through the generated launcher.

**Version 0.3:** for standalone CLIs, Intel/AMD processors, Linux, Windows, and experimental builds, use [the CLI/CPU guide](PORTABILITY.md). The desktop walkthrough below describes the previously validated Apple Silicon app path.

## 1. Choose what you need

| Your goal | Requirements | Expected result |
| --- | --- | --- |
| Check CLI compatibility | Python 3.9+ and an installed Codex CLI | A local report; no runtime changes |
| Understand or compare usage | Python 3.9+ and supported local JSONL logs | Token totals, cache coverage, errors, and observed changes |
| Try the runtime patch | CLI `0.154.0-alpha.6.2`, matching desktop app, Apple Silicon macOS, and build tools below | A separately built runtime you explicitly launch |
| Use Windows, Linux, Intel macOS, or a standalone CLI | See [PORTABILITY.md](PORTABILITY.md) | Diagnostics/reports plus experimental builds for source-checked releases; local validation is mandatory |

OpenCodex is optional; native `codex exec --json` captures also work. A CLI with native plugin support can install the plugin. Older CLIs can use the standalone scripts below. See [release evidence](RELEASES.md) for the tested scope.

## 2. Install and check

In a terminal, check for plugin commands, then install from GitHub:

```sh
codex plugin --help
codex plugin marketplace add NickDimitratos/codex-astra-cache-wait
codex plugin add astra-runtime-manager@astra-runtime
```

Start a **new Codex task/session** so it loads the installed skill. Paste:

> Use Astra Runtime Manager to check my CLI compatibility and runtime status. Explain what I can use on this machine.

**Expected result:** detected CLI versions and capabilities. On a first installation, runtime status normally shows `installed: false`. That refers to the separate runtime, even though the plugin is installed.

If `codex plugin` is unavailable, a different CLI may be first on your PATH. On macOS, check your desktop app's bundled executable, for example:

```sh
"/Applications/ChatGPT.app/Contents/Resources/codex" plugin --help
```

Use your actual app path and that executable for both install commands if it supports plugins. Plugin support does not imply runtime patch compatibility.

### Standalone tools without native plugins

With Git and Python 3.9+:

```sh
git clone https://github.com/NickDimitratos/codex-astra-cache-wait.git
cd codex-astra-cache-wait
python3 plugins/astra-runtime-manager/scripts/manage_runtime.py doctor
```

On Windows, use `python` if that is your Python 3.9+ command. Standalone commands below assume this repository directory. Installed plugin users can use the quoted requests; the skill locates its own scripts.

## 3. Set up the optional runtime

Skip this step for diagnostics/reporting only. If no compatible runtime is available, continue using those tools and normal Codex.

The current source build needs Python 3.11+, Git, `just`, Rustup with Rust 1.95.0, Apple's command-line developer tools, network access, and substantial free disk space. Compilation can take many minutes; there is no fixed completion time. No prebuilt desktop binaries are distributed.

On a supported installation, paste:

> Use Astra Runtime Manager to set up and enable the supported runtime, validate it, and give me its launcher. Keep my current tasks running and explain the manual restart step.

The skill checks prerequisites and [API/compaction limits](COMPATIBILITY.md), then runs `manage_runtime.py setup`. It builds and validates a separate runtime under `~/.local/share/codex-astra-cache-wait`. Repeating setup reuses a validated managed package when possible.

**Expected result:** setup succeeds, the launcher is enabled, and activation is **pending restart**. Your open Codex app continues using its existing runtime.

Standalone command on a supported Mac:

```sh
python3 plugins/astra-runtime-manager/scripts/manage_runtime.py setup
```

The manager detects a unique desktop app in common locations. If several apps exist, add `--app "/absolute/path/to/App.app"` with your actual path. A trusted local package can be imported with `setup --package "/absolute/path/to/package"`; it is copied and revalidated. Local validation does not establish another person's binary provenance.

Setup preserves the original app, PATH CLI, shell aliases, and global model/effort settings. `--root` selects a different dedicated directory; use the same `--root` for subsequent commands. Existing unowned directories are rejected.

## 4. Activate and verify

1. Finish active tasks and quit Codex completely.
2. Open the returned `launch-patched.command`. With the default directory, run in Terminal:

   ```sh
   "$HOME/.local/share/codex-astra-cache-wait/launch-patched.command"
   ```

3. After Codex reopens, paste:

   > Use Astra Runtime Manager to check whether the managed runtime is actually running. Show installed, enabled_for_launcher, running, and app_compatible separately.

| Status | Meaning | Next step |
| --- | --- | --- |
| `installed: true` | A validated runtime is on disk | Continue to launcher activation |
| `enabled_for_launcher: true` | The launcher selects it next time | Quit Codex and use that launcher |
| `running: true` | A managed runtime process was observed | Check model/API compatibility before measuring |
| `running: false` | No managed runtime process was observed | Check the launcher used and app compatibility |
| `running: null` | Process inspection failed | Activation is unknown; resolve the inspection error |
| `app_compatible: false` | The installed runtime does not match the app | Use normal Codex and recheck release support |

`app_compatible` appears once a runtime is installed. The launcher refuses to start while the app is open. Opening another window does not switch an already running app's runtime. Process detection cannot certify every request's model/provider configuration.

## 5. Everyday use

Start each desktop session where you want the patch through the generated launcher, then work in your usual projects. Your selected model and reasoning effort are preserved. The cache change applies only to the gated `gpt-6-astra` path in [COMPATIBILITY.md](COMPATIBILITY.md).

On a supported Mac, terminal users can start an interactive session through the managed wrapper:

```sh
"$HOME/.local/share/codex-astra-cache-wait/codex-patched"
```

Only sessions started through the wrapper use its runtime selection. Opening Codex normally uses its bundled runtime. If the app version changes, the wrapper falls back to the bundled CLI.

| When | Request to paste into Codex |
| --- | --- |
| After a restart | “Use Astra Runtime Manager to check whether the patched runtime is actually running.” |
| After a Codex update | “Use Astra Runtime Manager to check compatibility with my current app and CLI.” |
| When you have logs | “Use Astra Runtime Manager to summarize my usage log at [actual file path]. Show coverage and errors.” |
| When comparing runs | “Use Astra Runtime Manager to compare my before and after logs at [actual paths]. Separate observed changes from proven savings.” |
| Returning to normal Codex | “Use Astra Runtime Manager to disable the managed runtime and explain the restart step.” |

Replace bracketed descriptions with actual local paths. The plugin does not automatically collect logs, run shadow model calls, or schedule reports. Asking Codex to interpret results uses your normal assistant usage; the local diagnostic and reporting scripts themselves make **zero model calls**.

## 6. What to expect, including numbers

| Situation | Expected effect | Defensible number today |
| --- | --- | --- |
| Plugin installed; runtime inactive | Management/reporting tools become available | No runtime savings from installation alone |
| Run the local diagnostic or summarize existing logs | Local inspection and arithmetic | **0 additional model calls** from these scripts |
| Supported Astra work changes effort within a conversation | Patch aims to preserve cache reuse | Savings percentage **unknown** until matched trials are measured |
| Work waits for activity without an explicit deadline | Patch aims to avoid empty waits causing extra requests | Requests avoided depend on the task; **no fixed count** |
| Constant effort and no empty waits | The targeted causes may be absent | **Little or no benefit is possible** |
| Account allowance changes | Account-wide activity and accounting also affect it | **No verified allowance-saving percentage** |

The patch does not guarantee lower total tokens, faster completion, identical answers, or fixes for every HTTP 400/502 error. It does not configure OpenCodex routing, shadow-call models, or subscriptions. Evaluate task correctness alongside usage.

**No controlled live savings results have been established by this project yet.** The measurement guide's fabricated example goes from 1,000 to 300 fresh input tokens: a 70% decrease. This demonstrates arithmetic, **not an expected result for your installation**.

## 7. Measure your own results

1. Collect a baseline with the normal runtime for work you already intend to run.
2. Activate and verify the patched runtime, then run equivalent tasks in fresh threads and identical disposable project snapshots.
3. Keep CLI version, model, selected effort, tools, inputs, and success criteria comparable. Record differences.
4. Follow [the measurement guide](MEASUREMENTS.md) for exact capture/comparison commands and a demonstration requiring no model calls.
5. Check usage coverage, completed-task quality, errors, and repeated trials before drawing conclusions.

Benchmark tasks consume normal model usage. Reading existing captures does not. Native CLI reports count **threads** using final cumulative usage; OpenCodex reports count **requests**. These are different units.

Fresh input = input minus cached input for the same reported samples. Reasoning is already included in output. A higher cache percentage can coexist with higher overall usage if the workload grows. Missing values and causal/account savings remain unknown in reports.

Keep raw logs local: they can contain conversations and tool output. Usage reports export aggregates without prompts, raw errors, request IDs, or input file paths. Review aggregates before sharing. Diagnostic/status output includes local executable paths and needs separate review.

## 8. Update or uninstall

### Update the plugin

Use the same plugin-capable CLI used for installation:

```sh
codex plugin marketplace upgrade astra-runtime
codex plugin add astra-runtime-manager@astra-runtime
```

Start a new task/session. Updating the plugin refreshes tools and documentation; it does not silently replace or activate an installed runtime.

For an existing desktop runtime, ask the updated plugin to enable it again to refresh its generated launchers. Version 0.3.1 fixes a false "Codex is running" message caused by crash-reporting helpers that survive after quitting. This refresh verifies and preserves the installed runtime and its receipt; a desktop restart through the launcher is still required.

Version **0.3.2** refreshes both desktop and standalone launchers when enabling an existing runtime. After upgrading the plugin, ask: **“Enable my existing managed runtime again to refresh its launchers; keep my active tasks running.”** Then use the refreshed launcher for the next session. This does not rebuild the Rust package or change the current session.

The refreshed launchers check ownership and all recorded runtime file hashes before selecting the patch. A failed check produces a warning and uses the original CLI; recheck status before measuring usage. Verification adds local disk/CPU work per launch and makes no model calls. It detects changes against a local receipt; it does not authenticate downloaded binaries or prevent an attacker with control of that receipt from changing it. Desktop wrappers use the Python interpreter that generated them; if that interpreter is removed, regenerate the launchers with an available Python.

Setup now stages validation results, launchers, and the receipt before promoting the runtime. Caught promotion failures roll back completed steps so setup can be retried. Resolve the reported write error, then retry; a retained trusted package can be imported again. Power loss, forced termination, or rollback failure can still require inspection of the reported staging directory. Preserve unexpected files before recovery. Existing partial installations from older versions also require inspection before retrying.

After a Codex app update, run the diagnostic again. A matching tested catalog entry and runtime build are required. An older runtime cannot be enabled against a newer app, even if the catalog later adds support. Unsupported releases are not downgraded or forcibly patched.

### Temporarily use normal Codex

Ask **“Use Astra Runtime Manager to disable the managed runtime.”** Finish tasks, quit the patched instance, then open Codex normally. Disabling affects the next launch; it does not stop current processes.

### Remove the managed runtime and plugin

1. Disable the runtime, finish tasks, quit the patched instance, and open Codex normally.
2. In a new task, ask **“Use Astra Runtime Manager to remove its managed runtime, verify removal, then uninstall the plugin.”**
3. Runtime removal must succeed before uninstalling the plugin bundle. If you never set up a runtime, the normal plugin Uninstall action is sufficient.

Removal refuses to delete a running runtime, proceed with unknown process status, or discard unexpected files. The ordinary plugin toggle/Uninstall button manages the plugin bundle only. Older standalone builds outside the managed directory remain outside its ownership.

## Troubleshooting

| Symptom | Meaning / next step |
| --- | --- |
| `codex plugin` is unknown | Check the desktop's bundled CLI or use standalone tools in step 2 |
| Codex cannot find the skill | Confirm installation/enabling and start a new task/session |
| `runtime_patch_available: false` | Check `experimental_build_available` and upstream evidence; diagnostics/reports remain available |
| Unknown capabilities or `probe_note` | Check executable permissions and help/version commands; select it with `doctor --cli "/absolute/path/to/codex"` |
| No unique desktop app found | Pass your actual app path with `setup --app "/absolute/path/to/App.app"` |
| Missing build tools or a build error | Read the reported error/build log, resolve the prerequisite, and retry; incomplete setup is not active |
| Installed/enabled but not running | Follow step 4 and inspect `app_compatible` |
| Launcher says Codex is running | Finish tasks and quit the entire app. If it still refuses after quitting, update to plugin 0.3.1 or later and enable the runtime again to refresh the launcher; leftover framework crash reporters are ignored, while active workers still block launch |
| Behavior changes after an app update | Check compatibility; the wrapper may have fallen back to the bundled CLI |
| Usage fields are `null` or coverage is incomplete | The logs lack those measurements; this is not zero usage |
| Reporter rejects a file/output path | Use a supported JSONL format and a new output filename; existing files are not overwritten |
| Usage is unchanged or higher | Verify activation, equivalent workloads, cache warm-up, retries, and quality; savings are not guaranteed |
| Removal finds unexpected files | Preserve and inspect them before retrying; do not blindly delete an unowned directory |

For a reproducible problem, open a [GitHub issue](https://github.com/NickDimitratos/codex-astra-cache-wait/issues) with plugin/CLI versions, OS/architecture, the command or step, expected/actual behavior, and a redacted error or aggregate report. Exclude raw conversations, credentials, account identifiers, and personal paths.
