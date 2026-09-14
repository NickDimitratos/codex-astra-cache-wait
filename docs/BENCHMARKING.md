# Measure before claiming savings

Compare the bundled runtime and patched runtime using the same Codex version, model, reasoning effort, tools, task inputs, and success criteria. Record which runtime actually handled each trial. A package being built or a flag being written is not evidence of activation.

Use two kinds of workloads:

1. A controlled multi-turn task that changes reasoning effort between responses, to test the cache change.
2. A task that waits for long-running work without an explicit wait deadline, to test empty-wait behavior.

Also include a control task that uses constant effort and no long waits. Avoid unrelated concurrent tasks when measuring account-wide allowance. Repeat paired trials and alternate their order; cache warmth and model variation can otherwise dominate the result.

## Record per trial

| Field | Purpose |
| --- | --- |
| Runtime commit, flags, model, selected effort | Verify equivalent configuration |
| Completed task and quality checks | Avoid counting reduced work as optimization |
| Request count, errors, retries | Identify additional inference and failed work |
| Input and cached input tokens | Calculate fresh input and cache-hit rate |
| Output and reasoning tokens | Separate generated work from input caching |
| Wall time and empty wait results | Assess latency and idle behavior |
| Account allowance before/after and reset time | Keep quota observations separate |

Count each request once. If logs contain updates to a request, deduplicate by its identifier. Missing usage is unknown, not zero. Reasoning tokens are a subset of output tokens and must not be added twice. Cached input is a subset of input tokens; fresh input equals input minus cached input when both are reported consistently.

Report the distribution of comparable trials, not just a percentage from a single busy hour. Compare total usage per successfully completed task as well as cache-hit percentage. A higher cache-hit percentage can coexist with higher total consumption if there are more requests or larger prompts.

Do not infer Codex account allowance charges from API token prices. A change in account percentage across unrelated workloads is not a controlled benchmark.

Public reports should contain aggregate counts and synthetic reproduction steps. Keep raw prompts, account identifiers, request identifiers, tokens, headers, and local paths private.
