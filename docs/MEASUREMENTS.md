# Collect data and compare usage

Use Python 3.9+ and the plugin's `scripts/usage_report.py`. Commands below assume a repository clone. Installed skills resolve the script inside their own plugin bundle. On Windows use `python` if appropriate.

## Native CLI, without OpenCodex

Capture work you already intend to run. These capture commands run real tasks and consume normal model usage; the reporting tool itself makes no model calls. For reports only, `codex exec --json "Your agreed benchmark task" > before.jsonl` captures a task from your current CLI.

For a patch comparison, follow [setup and activation](COMMUNITY.md) first and use the **same supported CLI release** for both runs. The example below uses the current supported Mac app and the default managed directory. Adjust the app path if yours differs. Set the same model/effort and provider configuration for both runs; this comparison should use the supported Astra mode.

Run from a disposable benchmark project with your chosen task and a new output filename:

```sh
"/Applications/ChatGPT.app/Contents/Resources/codex" exec --json "Your agreed benchmark task" > before.jsonl
```

Save that capture, then use an identical fresh project snapshot and fresh thread for the after run. Confirm the managed runtime is enabled and matches the app before invoking its wrapper; the wrapper falls back to the original CLI when disabled or incompatible.

```sh
"$HOME/.local/share/codex-astra-cache-wait/codex-patched" exec --json "Your agreed benchmark task" > after.jsonl
```

Do not resume earlier threads. The shell's `>` redirection can overwrite a capture, so choose unused filenames and preserve each run separately. Using the normal CLI again for the after run measures another unpatched run. These generic captures show the workflow; a task must exercise the affected effort-change or wait behavior to test those changes.

Put the two captures in this toolkit's repository directory, or replace their names below with their actual paths. From this repository, summarize and compare:

```sh
python3 plugins/astra-runtime-manager/scripts/usage_report.py summarize before.jsonl --format codex-exec --output before.json
python3 plugins/astra-runtime-manager/scripts/usage_report.py summarize after.jsonl --format codex-exec --output after.json
python3 plugins/astra-runtime-manager/scripts/usage_report.py compare before.json after.json --output comparison.json
```

The native adapter reads `thread.started`, `turn.started`, `turn.completed`, and `turn.failed`. It keeps one final cumulative value per thread, including across concatenated captures of the same thread. It counts **threads**, not model requests. Repeated terminal events are ignored until another turn begins. Missing usage is unknown. Decreasing counters fail explicitly rather than guessing how to combine incompatible data. Resumed totals can include prior usage. Native events do not support trustworthy arbitrary time-window filtering.

If a later terminal event has no usable counters, the report retains the last known cumulative total as a **lower bound** and increments `samples_with_partial_usage`. A later valid cumulative total replaces that bound without double counting. `failed_samples` counts native threads containing an observed failed turn, even if they later recover. Token deltas remain unknown when either report includes a partial cumulative total.

See [RELEASES.md](RELEASES.md) for the checked schemas. An unknown output layout is not silently reported as zero.

## Optional OpenCodex request logs

```sh
python3 plugins/astra-runtime-manager/scripts/usage_report.py summarize /path/to/usage.jsonl --format opencodex --start 2026-09-14T10:00:00Z --end 2026-09-14T11:00:00Z --output before.json
```

Choose your actual start/end and a comparable after window. Start is inclusive; end is exclusive. Requests are deduplicated by request ID before aggregation. Attempt usage is not added again. Unclassified records remain separate. Retry counts are unknown when attempts are not recorded.

Reports expose token totals, model/effort grouping when available, failures, retry counts, and coverage. Failed requests without usage stay outside measured-token calculations. Cache ratio and fresh input per sample use the same subset with valid cache data. Missing reasoning fields do not mean zero reasoning.

Input/output differences and percentages are null when either report has no valid token measurements. An explicitly measured zero remains a known value. The model/effort warning compares sample proportions: a change from 90% Astra to 10% Astra is flagged even if both reports contain the same models; proportional growth in sample counts alone is not flagged as a mix change.

## Interpreting the comparison

- Fresh input = reported input minus reported cached input for the same samples.
- Reasoning is already included in output. Cached tokens are already included in input.
- Negative relative change means an observed decrease, not a proven causal saving.
- Task counts, context sizes, model/effort mix, concurrency, cache warm-up, retries, and missing usage can explain differences. Repeat matched task sets and check answer quality.
- Token totals alone cannot establish account allowance or dollar savings. Those fields remain unknown.

Record CLI version, platform, provider/model mode, effort, runtime activation evidence, workload, task quality, repetitions, and usage coverage alongside the aggregates. Native captures do not reliably identify model/effort; record them separately. Reports do not automatically verify runtime activation.

### A useful report to share

Copy this checklist alongside your aggregate report, filling in actual observations:

- Plugin version and both CLI versions:
- OS/architecture and provider/model/effort:
- How each runtime was launched and how activation was checked:
- Task description, success criteria, and whether both completed correctly:
- Repeated paired trials and their order:
- Sample unit/count, usage coverage, and missing measurements:
- Fresh input, cached input, output, errors/retries, and time per completed task where available:
- Workload/configuration differences and whether other account activity overlapped:

A decrease in one unmatched time window is an observation, not proof of a patch benefit. Only provide aggregate data and a redacted task description for public reports. Keep causal savings and account allowance conclusions unknown when the evidence cannot establish them.

## Reproduce a synthetic example

These commands consume no model usage. Output files are created without overwriting existing files; rename or remove your own prior outputs before repeating.

```sh
python3 plugins/astra-runtime-manager/scripts/usage_report.py summarize examples/synthetic-before.jsonl --format codex-exec --output before.json
python3 plugins/astra-runtime-manager/scripts/usage_report.py summarize examples/synthetic-after.jsonl --format codex-exec --output after.json
python3 plugins/astra-runtime-manager/scripts/usage_report.py compare before.json after.json
```

| Metric | Synthetic before | Synthetic after |
| --- | ---: | ---: |
| Threads | 2 | 2 |
| Input | 2,000 | 1,600 |
| Cached input | 1,000 | 1,300 |
| Fresh input | 1,000 | 300 |
| Output | 200 | 150 |

The example's 70% fresh-input reduction is **fabricated demonstration data, not a benchmark or product claim**. No measured patch savings are established. Original development observations made with the inactive patch do not demonstrate a benefit.

Raw JSONL contains task content and should stay local. Reports omit prompts, tool outputs, raw errors, IDs, and input file paths. Review aggregates before sharing. Diagnostic output includes executable locations, so review those separately before posting it.
