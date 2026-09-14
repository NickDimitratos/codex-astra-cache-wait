# Astra Runtime Manager

A community Codex plugin for CLI capability checks, private usage comparisons, and separate experimental runtime management. It provides a skill and local Python commands; it has no remote service, paid model endpoint, automatic startup hook, or credential store.

**[Start with the user guide](resources/COMMUNITY.md):** install → check compatibility → optionally set up → quit and launch → verify → measure. It includes copy-and-paste requests, expected status output, an expectations table, troubleshooting, and complete uninstall instructions.

Installing this plugin alone does not reduce usage. The local diagnostic/reporting scripts make zero model calls; conversations with Codex and benchmark tasks consume normal usage. No controlled live savings percentage is established, and little or no runtime benefit is possible for some workloads.

After installing from the GitHub marketplace, start a new Codex task and ask:

- “Check my Astra patch status.”
- “Check my CLI compatibility.”
- “Compare my before and after token usage.”
- “Set up the Astra runtime patch.”
- “Enable the Astra patch for my next Codex launch.”
- “Restore normal Codex and remove the managed runtime.”

Diagnostics and usage reports need Python 3.9+ and work independently of runtime patch support. They use native CLI JSONL or optional OpenCodex logs. See [measurement steps](resources/MEASUREMENTS.md) and [release evidence](resources/RELEASES.md).

The `setup` command builds a cataloged release or imports a trusted local package, validates it, and enables an explicit launcher. Use `--cli` for standalone setup on macOS/Linux/Windows or `--app` for Mac desktop integration. Source-checked candidates require `--experimental` and successful local validation. See [CLI/CPU setup](resources/PORTABILITY.md), [the desktop guide](resources/COMMUNITY.md), and [API limits](resources/COMPATIBILITY.md).

The plugin installs quickly; compiling the optional runtime is a separate, longer setup step. It does not run automatically when the plugin is installed. No prebuilt desktop binaries are redistributed here.

The managed runtime lives under `~/.local/share/codex-astra-cache-wait`. Setup and enablement never replace the original app or restart active tasks. A restart through the explicit launcher is required to activate the patch. Normal app launch restores the bundled runtime.

For complete removal, ask the plugin to remove its managed runtime before uninstalling the plugin. The ordinary plugin toggle/Uninstall button does not reverse external runtime setup. The original experimental runtime created outside this manager, if any, is also outside its ownership.

Source and attribution are in [LICENSE](resources/LICENSE) and [NOTICE](resources/NOTICE). The runtime changes are experimental and real token savings remain unmeasured.
