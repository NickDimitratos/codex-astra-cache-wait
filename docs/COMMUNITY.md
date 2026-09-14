# Setup, activation, and removal

Installing the plugin makes its commands available in new Codex tasks. Diagnostics and reporting work without a patched runtime. Runtime setup is a separate action followed by an explicit restart.

## Check your installation

Ask **“Use Astra Runtime Manager to check my CLI compatibility.”** It runs `manage_runtime.py doctor`. If PATH selects one release while the desktop bundles another, the report shows both. `doctor --cli /path/to/codex` selects one executable. A successful help probe does not certify runtime patch compatibility.

An unsupported runtime release can continue using reports. A CLI without native plugins can run the Python scripts from a repository clone. No automatic downgrade or forced patch is performed.

## Set up a supported runtime

Ask **“Set up and enable the supported Astra runtime, validate it, and give me its launcher.”** The skill runs `manage_runtime.py setup` from its installed plugin directory.

The manager detects a unique desktop app in common locations. If multiple apps are present, specify `--app /absolute/path/to/App.app`. No developer-specific account, source checkout, or home directory is assumed.

Setup checks the app version/platform against `resources/runtime-releases.json`. A first build needs Python 3.11+, Git, just, Rustup/Rust 1.95.0 for the current entry, Apple's command-line tools, network access, and substantial free space. Use `setup --package /path/to/package` to reuse a trusted existing package; it is copied and revalidated. A second setup reuses a validated managed installation instead of rebuilding it.

The default location is `~/.local/share/codex-astra-cache-wait`. Setup never replaces the signed app, PATH CLI, shell alias, or global model/effort settings. `--root` selects a different dedicated directory; existing unowned directories are rejected.

## Activate and confirm

1. Finish active tasks and quit Codex completely.
2. Open the generated `launch-patched.command`.
3. After reopening, ask **“Check whether my patched runtime is actually running.”**

| Status | Meaning |
| --- | --- |
| `installed` | A validated package is present |
| `enabled_for_launcher` | The explicit launcher selects it on the next launch |
| `running: true` | A process from the managed runtime was observed |
| `running: null` | Process inspection failed; activation is unknown |

The launcher refuses to start while the app is open. The `launch` command also works when the app is closed. On a compatible machine, the generated `codex-patched` wrapper can be used in a terminal. Only sessions started through the wrapper use the patch.

Use the API modes described in [COMPATIBILITY.md](COMPATIBILITY.md). Process detection cannot certify every request's model/provider configuration.

## Updates and removal

After a Codex update, run the diagnostic again. The wrapper falls back to the bundled CLI if its version changes. `enable` refuses an older installed runtime even if a new catalog entry supports the upgraded app. A matching tested entry and runtime build are required.

Ask **“Disable the Astra runtime.”** Then quit the patched instance and open Codex normally. Disabling changes the next wrapper launch; it does not stop running processes.

For full removal, ask **“Remove the managed runtime and uninstall Astra Runtime Manager.”** Removal refuses to proceed while the runtime is running, process inspection is unavailable, or unexpected files are present. After removal, uninstall the plugin bundle. The ordinary plugin toggle/Uninstall button does not remove external runtime files. Older standalone builds outside the manager's directory remain outside its ownership.
