# Changelog

## 0.3.0

- Add standalone `setup --cli`, portable Python launchers, and preserved original-CLI fallback after updates.
- Add native x86-64/ARM64 target selection for macOS, Linux GNU/musl, and Windows MSVC, preserving required sandbox helpers. Unknown CPUs remain unsupported.
- Add source-checked experimental build entries for stable `0.154.0` and additional platforms for the original release. These require explicit experimental setup and successful local validation; they are not certified cross-platform runtime builds.
- Record source evidence for older incompatible and newer upstream-fixed effort implementations. Do not force the original patch onto those releases.
- Inspect executable paths through macOS process listings, Linux procfs, and Windows CIM without reading process arguments. Add native CPU CI coverage and standalone setup documentation.

## Documentation update after 0.2.0

- Add a plain-language user walkthrough covering installation, compatibility, setup, actual activation, everyday use, updates, removal, and troubleshooting.
- Explain expected results and unknown savings, including the distinction between zero-call local reports and normal assistant/benchmark usage.
- Add baseline/patched capture commands and a checklist for useful community measurements. Bundle the same guidance with the installed plugin.

## 0.2.0

- Add CLI capability discovery across version numbers, with explicit unknown/unsupported states and PATH/desktop distinction.
- Select runtime compatibility through an extensible catalog of exact tested releases. Preserve old installation receipts and reject activation after an app version change.
- Add `setup` to validate and enable a separate runtime in one operation, reusing an existing managed package when possible. App location is detected or explicitly selectable.
- Add offline reports for native Codex exec JSONL and optional OpenCodex request logs, including cumulative-thread deduplication, coverage, errors, and comparison arithmetic.
- Add community setup, rollback, compatibility, and measurement guides with reproducible synthetic data.
- Expand Python CI to Linux, macOS, and Windows. The runtime patch remains validated only for its existing Apple Silicon macOS release; no universal runtime support or measured savings claim is added.

## 0.1.0

- Initial experimental source patch, guarded installation, local validation, and Codex plugin marketplace.
