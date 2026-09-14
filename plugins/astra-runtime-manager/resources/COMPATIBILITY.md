# Compatibility limits and release work

This is a source experiment for one release, not a general-purpose installer. An exact version match and passing local mock tests do not establish backend compatibility for every configuration.

## OpenAI API restrictions

The [reasoning documentation](https://developers.openai.com/api/docs/guides/reasoning#change-reasoning-mid-conversation), checked on 2026-09-14, limits configuration updates to Astra's standard single-agent API mode. They change reasoning effort only. The documentation also rejects adjacent configuration updates, automatic compaction/truncation combined with these updates, and update-containing histories sent to the standalone compact endpoint. Explicit compaction using a compaction trigger in a Responses request is supported.

These restrictions apply to the cache feature. Do not infer support for Pro or other API modes from the fact that the model name matches. The patch's existing model/provider/transport checks are not a complete proof that every API mode is compatible.

## Compaction in the pinned source

The pinned release enables `remote_compaction_v2` by default. Its V2 implementation appends a compaction trigger to a Responses request. The legacy path used when that feature is disabled sends history through the standalone compact operation. That legacy path should not be used with `reasoning_effort_override` enabled.

Source locations in the pinned upstream repository:

- `codex-rs/core/src/session/turn.rs`: selects the compaction path.
- `codex-rs/core/src/compact_remote_v2_attempt.rs`: appends the explicit compaction trigger.
- `codex-rs/core/src/compact_remote_request.rs`: submits history to the legacy compact operation.
- `codex-rs/features/src/lib.rs`: defaults for `remote_compaction_v2`.

An API's automatic compaction setting and Codex deciding locally to send an explicit compaction request are different mechanisms. Do not disable all context management based only on the API restriction.

The patch tests the effort anchor after surviving history is replaced; that unit check is not an end-to-end backend compaction test. Before a stable release, add dedicated coverage for compaction with effort changes, the legacy path, interrupted turns that could leave adjacent updates, and transitions between supported and unsupported modes. The package smoke tests do not send requests to OpenAI and cannot establish acceptance by a live backend.

## Stable release criteria

- Explicit compatibility checks and regression coverage for the restrictions above.
- Comparable before/after measurements that preserve task quality.
- Runtime validation on every platform advertised as supported.
- Review against newer upstream releases and removal of patches already fixed upstream.

Until then, publish and describe this as an experimental patch for developers, with no guaranteed savings percentage.
