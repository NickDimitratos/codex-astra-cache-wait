#!/usr/bin/env python3
"""Aggregate local usage without exporting prompts, paths, IDs, or credentials."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path


def timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError("Invalid timestamp")
        return value / 1000  # OpenCodex timestamps are milliseconds.
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamps must include a timezone")
        return parsed.timestamp()
    raise ValueError("Missing timestamp")


def usage_values(usage, camel=False):
    if not isinstance(usage, dict):
        return None
    keys = ("inputTokens", "outputTokens", "cachedInputTokens", "reasoningOutputTokens") if camel else (
        "input_tokens", "output_tokens", "cached_input_tokens", "reasoning_output_tokens")
    values = [usage.get(key) for key in keys]
    if camel and values[2] is None:
        values[2] = usage.get("cacheReadInputTokens")
    def valid(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if not all(valid(value) for value in values[:2]):
        return None
    for index, maximum in ((2, values[0]), (3, values[1])):
        if values[index] is not None and (not valid(values[index]) or values[index] > maximum):
            return None
    return dict(zip(("input", "output", "cached", "reasoning"), values))


def read_events(path, format_name, start=None, end=None):
    if format_name == "codex-exec" and (start is not None or end is not None):
        raise ValueError("Codex exec events have no reliable timestamps; use separate files for each run")
    if start is not None and end is not None and end <= start:
        raise ValueError("End must be later than start")
    quality = Counter()
    records, events, native_threads = {}, [], {}
    native_thread = "capture-without-thread-header"
    active_turn = True  # Older captures can start at the first completed turn.
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError()
            except ValueError:
                quality["malformed_lines"] += 1
                continue
            if format_name == "opencodex":
                rid = row.get("requestId")
                if not isinstance(rid, str) or not rid:
                    quality["records_without_request_id"] += 1
                    continue
                quality["duplicate_request_records_replaced"] += rid in records
                records[rid] = row
                continue
            kind = row.get("type")
            if kind == "thread.started":
                identifier = row.get("thread_id")
                if not isinstance(identifier, str) or not identifier:
                    raise ValueError("Native thread.started event has no thread_id")
                native_thread = identifier
                active_turn = True
            elif kind == "turn.started":
                active_turn = True
            elif kind in ("turn.completed", "turn.failed"):
                if not active_turn:
                    quality["duplicate_terminal_events_ignored"] += 1
                    continue
                active_turn = False
                current_usage = usage_values(row.get("usage"))
                previous = native_threads.get(native_thread, {})
                prior = previous.get("usage")
                if prior and current_usage and any(current_usage[k] < prior[k] for k in ("input", "output")):
                    raise ValueError("Native thread totals decreased; use fresh thread captures or a matching format adapter")
                native_threads[native_thread] = {"model": "unspecified", "effort": "unspecified",
                               "usage": current_usage or prior,
                               "usage_is_lower_bound": current_usage is None and prior is not None,
                               "error": previous.get("error", False) or kind == "turn.failed",
                               "extra_sends": None}
                quality["native_terminal_events"] += 1
            elif kind == "error":
                quality["stream_error_events"] += 1  # May duplicate turn.failed; no extra request inferred.
            else:
                quality["non_usage_events_ignored"] += 1
    for row in records.values():
        if start is not None or end is not None:
            try:
                when = timestamp(row.get("timestamp"))
            except (ValueError, OverflowError):
                quality["records_without_valid_timestamp"] += 1
                continue
            if (start is not None and when < start) or (end is not None and when >= end):
                continue
        if (not row.get("requestedModel") and row.get("usageStatus") != "reported" and not row.get("attempts")
                and usage_values(row.get("usage"), camel=True) is None):
            quality["unclassified_transport_records"] += 1
            continue
        usage = usage_values(row.get("usage"), camel=True) if row.get("usageStatus") in (None, "reported") else None
        attempts = row.get("attempts")
        sends = None
        if isinstance(attempts, list) and attempts:
            counts = [a.get("sendCount", 1) if isinstance(a, dict) else None for a in attempts]
            if all(isinstance(n, int) and not isinstance(n, bool) and n >= 1 for n in counts):
                sends = max(0, sum(counts) - 1)
        model = row.get("resolvedModel") or row.get("model") or row.get("requestedModel") or "unspecified"
        effort = row.get("requestedEffort") or "unspecified"
        # Arbitrary provider/model names can contain user data. Only expose known structural slugs.
        model = model if isinstance(model, str) and model.startswith("gpt-") and len(model) < 80 and all(c.isalnum() or c in "-._" for c in model) else "other-or-unspecified"
        effort = effort if effort in ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra") else "unspecified"
        status = row.get("status")
        events.append({"model": model, "effort": effort, "usage": usage,
                       "error": status not in (200, "200", None), "status_missing": status is None,
                       "extra_sends": sends})
    events.extend(native_threads.values())
    if not events:
        raise ValueError("No recognized usage/terminal records found; choose the matching format or export codex exec --json")
    return events, dict(quality)


def summarize(events):
    counts = Counter(samples=len(events))
    for event in events:
        counts["failed_samples"] += event["error"]
        counts["samples_without_status"] += event.get("status_missing", False)
        if event["extra_sends"] is None:
            counts["samples_without_retry_data"] += 1
        else:
            counts["extra_sends_reported"] += event["extra_sends"]
        usage = event["usage"]
        counts["samples_with_partial_usage"] += event.get("usage_is_lower_bound", False)
        if usage is None:
            counts["samples_without_valid_usage"] += 1
            continue
        counts["samples_with_usage"] += 1
        counts["input_tokens_reported"] += usage["input"]
        counts["output_tokens_reported"] += usage["output"]
        if usage["cached"] is not None:
            counts["samples_with_cache_usage"] += 1
            counts["input_tokens_with_cache_usage"] += usage["input"]
            counts["cached_input_tokens_reported"] += usage["cached"]
            counts["fresh_input_tokens_reported"] += usage["input"] - usage["cached"]
        if usage["reasoning"] is not None:
            counts["samples_with_reasoning_usage"] += 1
            counts["reasoning_tokens_subset_of_output"] += usage["reasoning"]
    keys = ("samples", "failed_samples", "samples_without_status", "samples_without_retry_data", "extra_sends_reported",
            "samples_without_valid_usage", "samples_with_usage", "samples_with_partial_usage", "input_tokens_reported",
            "output_tokens_reported", "samples_with_cache_usage", "input_tokens_with_cache_usage",
            "cached_input_tokens_reported", "fresh_input_tokens_reported", "samples_with_reasoning_usage",
            "reasoning_tokens_subset_of_output")
    result = {key: counts[key] for key in keys}
    result["cache_percent_reported_subset"] = (100 * counts["cached_input_tokens_reported"] /
        counts["input_tokens_with_cache_usage"] if counts["input_tokens_with_cache_usage"] else None)
    result["fresh_input_per_cache_reported_sample"] = (counts["fresh_input_tokens_reported"] /
        counts["samples_with_cache_usage"] if counts["samples_with_cache_usage"] else None)
    return result


def report(path, format_name, start=None, end=None):
    events, quality = read_events(path, format_name, start, end)
    groups = defaultdict(list)
    for event in events:
        groups[event["model"]].append(event)
    return {"schema_version": 1, "format": format_name,
            "sample_unit": "requests" if format_name == "opencodex" else "threads",
            "usage_scope": "request-window" if format_name == "opencodex" else "thread-cumulative",
            "window": {"start_epoch_seconds": start, "end_epoch_seconds": end},
            "totals": summarize(events),
            "by_model": {model: summarize(rows) for model, rows in sorted(groups.items())},
            "effort_samples": dict(Counter(event["effort"] for event in events)),
            "quality": quality, "runtime_activation_verified": False,
            "causal_savings_percent": None,
            "notes": ["Only numeric aggregates and restricted model/effort names are exported.",
                      "Missing usage is unknown, not zero. Cache and reasoning coverage are explicit.",
                      "Partial native usage retains the last known cumulative lower bound; later unmeasured usage is unknown.",
                      "Reasoning is included in output; cached input is included in input.",
                      "Codex exec totals are cumulative per thread; resumed threads may include earlier usage. Use fresh threads for benchmarks.",
                      "Token totals cannot establish account allowance or monetary savings."]}


def compare(before, after):
    if any(item.get("schema_version") != 1 for item in (before, after)):
        raise ValueError("Unsupported report schema")
    if (before["format"], before["sample_unit"]) != (after["format"], after["sample_unit"]):
        raise ValueError("Compare reports from the same format and sample unit")
    changes = {}
    for key in ("samples", "input_tokens_reported", "output_tokens_reported", "fresh_input_tokens_reported",
                "fresh_input_per_cache_reported_sample", "cache_percent_reported_subset"):
        a, b = before["totals"][key], after["totals"][key]
        known = a is not None and b is not None
        if key != "samples":
            known = known and all(item["totals"]["samples_with_usage"] > 0 and
                                  not item["totals"].get("samples_with_partial_usage", 0)
                                  for item in (before, after))
        if key == "fresh_input_tokens_reported":
            known = known and all(item["totals"]["samples_with_cache_usage"] > 0 for item in (before, after))
        changes[key] = {"before": a, "after": b,
                        "difference": b - a if known else None,
                        "relative_change_percent": 100 * (b - a) / a if known and a else None}
    notes = ["Observed changes only. These reports do not verify activation, equivalent tasks, or answer quality.",
             "Use comparable task sets, model, effort, concurrency, and context size; record runtime evidence separately."]
    def different_proportions(a, b):
        total_a, total_b = sum(a.values()), sum(b.values())
        return set(a) != set(b) or any(a[key] * total_b != b[key] * total_a for key in a)

    if (different_proportions(before["effort_samples"], after["effort_samples"]) or
            different_proportions({model: group["samples"] for model, group in before["by_model"].items()},
                                  {model: group["samples"] for model, group in after["by_model"].items()})):
        notes.append("Model or effort sample mix differs; aggregated changes are not directly comparable.")
    if any(item["totals"]["samples_without_valid_usage"] or
           item["totals"].get("samples_with_partial_usage", 0) or
           item["totals"]["samples_with_cache_usage"] != item["totals"]["samples"] for item in (before, after)):
        notes.append("Usage coverage is incomplete; some token comparisons cover reported subsets only.")
    if any(item["totals"].get("samples_with_partial_usage", 0) for item in (before, after)):
        notes.append("Native totals include lower bounds; token deltas are unknown until complete cumulative usage is available.")
    return {"schema_version": 1, "sample_unit": before["sample_unit"], "observed_changes": changes,
            "causal_savings_percent": None, "account_allowance_savings_percent": None, "notes": notes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("log", type=Path)
    summarize_parser.add_argument("--format", choices=("codex-exec", "opencodex"), required=True)
    summarize_parser.add_argument("--start", type=timestamp)
    summarize_parser.add_argument("--end", type=timestamp)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    for command in (summarize_parser, compare_parser):
        command.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = (report(args.log, args.format, args.start, args.end) if args.action == "summarize"
                  else compare(json.loads(args.before.read_text(encoding="utf-8")),
                               json.loads(args.after.read_text(encoding="utf-8"))))
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        else:
            print(serialized, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Usage report: {error}\n")


if __name__ == "__main__":
    main()
