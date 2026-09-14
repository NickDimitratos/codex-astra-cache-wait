# Astra Runtime Manager

A community Codex plugin for CLI capability checks, private usage comparisons, and separate experimental runtime management. It provides a skill and local Python commands; it has no remote service, paid model endpoint, automatic startup hook, or credential store.

After installing from the GitHub marketplace, start a new Codex task and ask:

- “Check my Astra patch status.”
- “Check my CLI compatibility.”
- “Compare my before and after token usage.”
- “Set up the Astra runtime patch.”
- “Enable the Astra patch for my next Codex launch.”
- “Restore normal Codex and remove the managed runtime.”

Diagnostics and usage reports need Python 3.9+ and work independently of runtime patch support. They use native CLI JSONL or optional OpenCodex logs. See [measurement steps](resources/MEASUREMENTS.md) and [release evidence](resources/RELEASES.md).

The `setup` command builds a tested release or imports a trusted local package, validates it, and enables the explicit launcher. The current runtime entry needs Apple Silicon macOS and the matching Codex release. Source compilation needs Python 3.11+, Git, just, Rustup/Rust 1.95.0, and Apple's command-line tools. See [setup and rollback](resources/COMMUNITY.md) and [API limits](resources/COMPATIBILITY.md). Unsupported releases get diagnostics and reports; they are not silently patched or downgraded.

The plugin installs quickly; compiling the optional runtime is a separate, longer setup step. It does not run automatically when the plugin is installed. No prebuilt desktop binaries are redistributed here.

The managed runtime lives under `~/.local/share/codex-astra-cache-wait`. Setup and enablement never replace the original app or restart active tasks. A restart through the explicit launcher is required to activate the patch. Normal app launch restores the bundled runtime.

For complete removal, ask the plugin to remove its managed runtime before uninstalling the plugin. The ordinary plugin toggle/Uninstall button does not reverse external runtime setup. The original experimental runtime created outside this manager, if any, is also outside its ownership.

Source and attribution are in [LICENSE](resources/LICENSE) and [NOTICE](resources/NOTICE). The runtime changes are experimental and real token savings remain unmeasured.
