# Verification record

Recorded on 2026-09-14 against the commit in `compatibility.json`, on Apple Silicon macOS. These are observations from the initial development environment, not results from a published CI run.

## Runtime changes

- 24 focused regression/compatibility checks passed, including resume and fork behavior.
- The complete `just test` build was attempted. Unavailable `pkg-config`/GLib/GStreamer >=1.28 dependencies blocked `codex-voice-host`.
- With only `codex-voice-host` excluded, 17,553 tests ran: 17,501 passed, 50 failed, and two timed out. Another 45 tests were skipped.
- The 52 failures/timeouts were rerun against the exact unmodified release: 40 failed there too, and 12 passed with reduced concurrency.
- Those 12 and the 24 focused checks then passed together on patched source with two test threads and no retries: **36/36**.
- `just fmt`, `just write-config-schema`, scoped Clippy fixes, and a final diff check passed. An unrelated automatic unused-import cleanup was reverted.
- The optimized release package built. A local mock exercised actual Code Mode execution; app-server initialization and feature selection also passed. The selected model and effort remained Astra XHigh.

The Rust patch distributed here is byte-for-byte the patch used for that validation. Its SHA-256 is in `compatibility.json`. The original release lockfile was restored after a temporary normalization of local workspace package versions; no external dependency changes are included.

## Toolkit checks

The guard's tests use temporary Git repositories and check that incompatible versions, existing edits, untracked files, subdirectories, repeated application, and changed patch bytes are rejected without losing user work. A check-only run must leave source unchanged. Patch application is also checked against the pinned upstream source.

Run:

```sh
python3 -m unittest discover -s tests -v
```

Portable package smoke scripts use a temporary Codex home. `package_smoke.py` uses fake credentials and a loopback mock; it deliberately routes attempted external HTTP calls to the mock. Plugin refresh warnings from blocked external calls do not establish a model failure. `app_server_smoke.py` initializes the protocol and reads configuration without creating a model turn.

## Plugin manager checks

- 28 Python checks passed across the guard, manager, and self-contained plugin bundle. They cover ownership, checksum failures, unsupported versions, concurrent operations, active-runtime removal, and unexpected file preservation.
- The official Codex plugin and skill validators accepted the bundle.
- A temporary managed installation imported the previously built package and reran both package checks successfully. Enablement stayed separate from actual runtime activation.
- The generated launcher refused to open a patched instance while the desktop app was running. Disabling it made the wrapper use the original bundled CLI.
- Removal deleted the temporary managed directory while preserving the existing development runtime and installed app.

The manager's source-build command uses the same pinned upstream assembly path used for the earlier release build. The lifecycle check reused that local package; it did not perform a second full source build or restart the desktop app.

## What remains unproven

No controlled measurement has established token savings, improved account allowance, live backend compatibility for every reasoning mode, or unchanged task quality across workloads. A previous usage observation happened before activation and cannot establish causality. Full-suite success and runtime compatibility on other operating systems are also unproven.

The configuration flags remain marked under development. Do not use this record to describe the patch as a stable or universal release.
