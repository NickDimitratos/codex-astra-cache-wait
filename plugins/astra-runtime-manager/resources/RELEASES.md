# Compatibility and evidence

The plugin probes capabilities without a fixed version gate. Runtime setup still needs an exact release manifest. [PORTABILITY.md](PORTABILITY.md) records source evidence, standalone setup, native target adapters, and the experimental validation scope.

| Release | Capability probe | Native usage schema | Runtime patch |
| --- | --- | --- | --- |
| `0.153.4` | Tested locally; plugins and exec JSON found | Official source inspected; cumulative thread totals | No approved patch entry |
| `0.154.0-alpha.6.2` | Tested locally; plugins and exec JSON found | Official source inspected; cumulative thread totals | Desktop and standalone lifecycle validated on Apple Silicon; other target builds require local validation |
| `0.154.0` | Probed at setup | Recognized schema required | Patch applies to exact stable source; experimental native builds require local validation |
| `0.155.0-alpha.4` | Probed at setup | Recognized schema required | Upstream request-effort pinning is present; older patch is refused |
| Other releases | Best-effort version/help probes; unavailable capabilities remain unknown | Accepted only when the documented layout matches; unknown layouts fail explicitly | Requires an exact tested catalog entry |

Native source references: [0.153.4 output emitter](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/exec/src/event_processor_with_jsonl_output.rs) and [0.154.0-alpha.6.2 output emitter](https://github.com/openai/codex/blob/rust-v0.154.0-alpha.6.2/codex-rs/exec/src/event_processor_with_jsonl_output.rs). Both emit `usage.total` at completion. Reports retain the latest cumulative value per thread. A resumed thread can include history predating the capture.

## Adding runtime releases

The catalog is `plugins/astra-runtime-manager/resources/runtime-releases.json`. Each entry selects a release and either one platform or an explicit target list, plus a source manifest, package version, toolchain, and evidence description. Entries marked `local_validation_required` need experimental opt-in. The manifest pins the upstream commit and patch checksum. Stable releases, prereleases, custom builds, and architectures are not interchangeable.

Port and review the patch on the desired release; test its behaviors and API-mode restrictions; build the package; verify protocol, Code Mode, activation, and rollback; record the evidence. Add build/format adapters when upstream behavior differs. Passing `git apply --check` or seeing a feature name in CLI help is insufficient.

The build adapter uses upstream's canonical package assembler. Desktop builds reuse the matching app's Code Mode host; standalone builds let upstream build its host and platform helpers. Standalone import/activation/rollback passed locally with the existing Apple Silicon package. Source builds without a supplied host and other native platforms remain experimental and require local validation. Toolkit CI and runtime evidence remain separate.

No measured patch savings are established. Community benchmarks must record activation, model/provider mode, effort, task quality, comparable workloads, usage coverage, and repeated runs. Keep raw conversations and authentication material out of public submissions.
