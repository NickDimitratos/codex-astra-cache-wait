# Contributing

Keep changes focused on the two behaviors in the README. Preserve the selected model, effort, explicit timeout semantics, existing user data, and upstream provider/transport compatibility gates.

For a new supported release, reproduce the problem on its unmodified source first. Inspect whether upstream has already fixed it. Port the patch deliberately, update the exact commit and checksum, and run the relevant Rust checks and package tests. Do not broaden compatibility merely because a patch applies without conflicts.

For a bug report, include the runtime version, operating system/architecture, enabled flags, synthetic reproduction steps, and expected/actual behavior. Include whether it also occurs on the unmodified release. Share only sanitized excerpts.

For token measurements, follow `docs/BENCHMARKING.md`. Report unsuccessful tasks and missing data; do not advertise guaranteed savings or a quota-accounting defect without evidence.

Run the toolkit tests with `python3 -m unittest discover -s tests -v`. Follow the pinned upstream repository's `AGENTS.md` for Rust changes. The lightweight CI workflow does not replace the runtime test suite.
