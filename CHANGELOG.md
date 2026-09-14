# Changelog

## 0.2.0

- Add CLI capability discovery across version numbers, with explicit unknown/unsupported states and PATH/desktop distinction.
- Select runtime compatibility through an extensible catalog of exact tested releases. Preserve old installation receipts and reject activation after an app version change.
- Add `setup` to validate and enable a separate runtime in one operation, reusing an existing managed package when possible. App location is detected or explicitly selectable.
- Add offline reports for native Codex exec JSONL and optional OpenCodex request logs, including cumulative-thread deduplication, coverage, errors, and comparison arithmetic.
- Add community setup, rollback, compatibility, and measurement guides with reproducible synthetic data.
- Expand Python CI to Linux, macOS, and Windows. The runtime patch remains validated only for its existing Apple Silicon macOS release; no universal runtime support or measured savings claim is added.

## 0.1.0

- Initial experimental source patch, guarded installation, local validation, and Codex plugin marketplace.
