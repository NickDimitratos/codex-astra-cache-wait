# Compatibility and evidence

The plugin inspects releases without a hard-coded version gate. The Rust source patch still requires exact compatibility. Older CLIs can lack plugins or JSON usage; future releases can change schemas or already fix the underlying behavior.

| Release | Capability probe | Native usage schema | Runtime patch |
| --- | --- | --- | --- |
| `0.153.4` | Tested locally; plugins and exec JSON found | Official source inspected; cumulative thread totals | No approved patch entry |
| `0.154.0-alpha.6.2` | Tested locally; plugins and exec JSON found | Official source inspected; cumulative thread totals | Tested on Apple Silicon macOS with matching desktop app; experimental |
| Other releases | Best-effort version/help probes; unavailable capabilities remain unknown | Accepted only when the documented layout matches; unknown layouts fail explicitly | Requires an exact tested catalog entry |

Native source references: [0.153.4 output emitter](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/exec/src/event_processor_with_jsonl_output.rs) and [0.154.0-alpha.6.2 output emitter](https://github.com/openai/codex/blob/rust-v0.154.0-alpha.6.2/codex-rs/exec/src/event_processor_with_jsonl_output.rs). Both emit `usage.total` at completion. Reports retain the latest cumulative value per thread. A resumed thread can include history predating the capture.

## Adding runtime releases

The catalog is `plugins/astra-runtime-manager/resources/runtime-releases.json`. Each entry selects one version/platform pair, source manifest, package version, toolchain, and evidence description. The manifest includes exact upstream commit and patch checksum. Stable releases, prereleases, custom builds, and architectures are not interchangeable.

Port and review the patch on the desired release; test its behaviors and API-mode restrictions; build the package; verify protocol, Code Mode, activation, and rollback; record the evidence. Add build/format adapters when upstream behavior differs. Passing `git apply --check` or seeing a feature name in CLI help is insufficient.

The current build adapter uses upstream's canonical package assembler and the matching desktop Code Mode host. CLI-only source builds without a desktop app and other operating systems remain unvalidated for runtime activation. Offline reporting and diagnostic arithmetic have separate cross-platform checks.

No measured patch savings are established. Community benchmarks must record activation, model/provider mode, effort, task quality, comparable workloads, usage coverage, and repeated runs. Keep raw conversations and authentication material out of public submissions.
