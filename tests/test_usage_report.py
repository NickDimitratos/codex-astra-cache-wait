import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("community_usage", ROOT / "plugins/astra-runtime-manager/scripts/usage_report.py")
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "events.jsonl"

    def report(self, rows, format_name="codex-exec", **kwargs):
        self.path.write_text("\n".join(json.dumps(row) for row in rows))
        return usage.report(self.path, format_name, **kwargs)

    def turn(self, input=1000, cached=800, output=100, reasoning=20):
        return {"type": "turn.completed", "usage": {"input_tokens": input, "cached_input_tokens": cached,
                "output_tokens": output, "reasoning_output_tokens": reasoning}}

    def request(self, rid="a", **extra):
        return dict({"requestId": rid, "timestamp": 1000, "requestedModel": "gpt-6-astra", "status": 200,
                     "usageStatus": "reported", "usage": {"inputTokens": 1000, "cachedInputTokens": 800,
                     "outputTokens": 100, "reasoningOutputTokens": 20}, "attempts": [{"sendCount": 1}]}, **extra)

    def test_exec_counts_threads_and_does_not_double_add_reasoning(self):
        result = self.report([self.turn()])
        self.assertEqual(result["sample_unit"], "threads")
        self.assertEqual(result["totals"]["fresh_input_tokens_reported"], 200)
        self.assertEqual(result["totals"]["output_tokens_reported"], 100)
        self.assertEqual(result["totals"]["reasoning_tokens_subset_of_output"], 20)
        self.assertIsNone(result["causal_savings_percent"])

    def test_duplicate_terminal_ignored_and_cumulative_thread_not_double_counted(self):
        result = self.report([self.turn(), self.turn(), {"type": "turn.started"}, self.turn(input=1200)])
        self.assertEqual(result["totals"]["samples"], 1)
        self.assertEqual(result["totals"]["input_tokens_reported"], 1200)

    def test_resumed_thread_counts_latest_total_once(self):
        result = self.report([{"type":"thread.started","thread_id":"a"}, self.turn(),
                              {"type":"thread.started","thread_id":"a"}, self.turn(input=1500)])
        self.assertEqual(result["totals"]["input_tokens_reported"], 1500)

    def test_different_threads_are_added(self):
        result = self.report([{"type":"thread.started","thread_id":"a"}, self.turn(),
                              {"type":"thread.started","thread_id":"b"}, self.turn()])
        self.assertEqual(result["totals"]["samples"], 2)
        self.assertEqual(result["totals"]["input_tokens_reported"], 2000)

    def test_decreasing_native_totals_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "decreased"):
            self.report([self.turn(), {"type":"turn.started"}, self.turn(input=900)])

    def test_older_exec_missing_cache_and_reasoning_are_unknown(self):
        result = self.report([{"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10}}])
        self.assertEqual(result["totals"]["samples_with_usage"], 1)
        self.assertEqual(result["totals"]["samples_with_cache_usage"], 0)
        self.assertIsNone(result["totals"]["cache_percent_reported_subset"])

    def test_failed_request_does_not_enter_cache_denominator(self):
        result = self.report([self.request(), self.request("b", usageStatus="unreported", usage=None, status=502)], "opencodex")
        self.assertEqual(result["totals"]["samples"], 2)
        self.assertEqual(result["totals"]["samples_with_usage"], 1)
        self.assertEqual(result["totals"]["fresh_input_per_cache_reported_sample"], 200)
        self.assertEqual(result["totals"]["failed_samples"], 1)

    def test_request_dedup_and_retry_usage_counted_once(self):
        row = self.request(attempts=[{"sendCount": 2, "usage": {"inputTokens": 999999}}])
        result = self.report([row, row], "opencodex")
        self.assertEqual(result["totals"]["input_tokens_reported"], 1000)
        self.assertEqual(result["totals"]["extra_sends_reported"], 1)

    def test_report_does_not_export_prompts_paths_ids_or_errors(self):
        secret = "PRIVATE-CONTENT-1234"
        result = self.report([self.request(secret, conversationId=secret, prompt=secret, error=secret, path=secret)], "opencodex")
        self.assertNotIn(secret, json.dumps(result))

    def test_unknown_model_strings_are_not_exported(self):
        result = self.report([self.request(model="private@email.example", requestedModel="private@email.example")], "opencodex")
        self.assertNotIn("private@email.example", json.dumps(result))

    def test_invalid_usage_is_excluded(self):
        for row in [self.turn(cached=1001), self.turn(reasoning=101), self.turn(input=-1), self.turn(input=True)]:
            result = self.report([row])
            self.assertEqual(result["totals"]["samples_without_valid_usage"], 1)

    def test_older_cache_alias_and_missing_status_are_supported(self):
        row = {"requestId":"old", "model":"gpt-6-astra", "usage":{
            "inputTokens":1000,"cacheReadInputTokens":700,"outputTokens":100}}
        result = self.report([row], "opencodex")
        self.assertEqual(result["totals"]["fresh_input_tokens_reported"], 300)
        self.assertEqual(result["totals"]["samples_without_status"], 1)
        self.assertEqual(result["totals"]["samples_without_retry_data"], 1)

    def test_unclassified_records_outside_window_are_excluded(self):
        result = self.report([self.request(), {"requestId":"transport", "timestamp":3000}], "opencodex", start=1,end=2)
        self.assertEqual(result["quality"].get("unclassified_transport_records",0),0)

    def test_example_files_match_documented_numbers(self):
        before = usage.report(ROOT / 'examples/synthetic-before.jsonl', 'codex-exec')
        after = usage.report(ROOT / 'examples/synthetic-after.jsonl', 'codex-exec')
        self.assertEqual(before['totals']['input_tokens_reported'],2000)
        self.assertEqual(before['totals']['fresh_input_tokens_reported'],1000)
        self.assertEqual(after['totals']['input_tokens_reported'],1600)
        self.assertEqual(after['totals']['fresh_input_tokens_reported'],300)
        self.assertEqual(after['totals']['output_tokens_reported'],150)

    def test_time_window_is_start_inclusive_end_exclusive(self):
        result = self.report([self.request("a", timestamp=1000), self.request("b", timestamp=2000), self.request("c", timestamp=3000)], "opencodex", start=1, end=3)
        self.assertEqual(result["totals"]["samples"], 2)

    def test_exec_time_filter_rejected(self):
        with self.assertRaisesRegex(ValueError, "timestamps"):
            self.report([self.turn()], start=1)

    def test_unknown_format_data_is_not_silently_zero(self):
        with self.assertRaisesRegex(ValueError, "No recognized"):
            self.report([{"new_event": "usage-schema-changed"}])

    def test_comparison_preserves_unknown_savings_and_zero_denominators(self):
        before = self.report([self.turn(input=0, cached=0)])
        after = self.report([self.turn()])
        result = usage.compare(before, after)
        self.assertIsNone(result["observed_changes"]["input_tokens_reported"]["relative_change_percent"])
        self.assertIsNone(result["causal_savings_percent"])
        self.assertIsNone(result["account_allowance_savings_percent"])

    def test_cannot_compare_requests_to_threads(self):
        with self.assertRaisesRegex(ValueError, "same format"):
            usage.compare(self.report([self.turn()]), self.report([self.request()], "opencodex"))

    def test_numeric_comparison(self):
        before = self.report([self.turn(input=1000, cached=500)])
        after = self.report([self.turn(input=800, cached=650)])
        result = usage.compare(before, after)
        self.assertEqual(result["observed_changes"]["fresh_input_tokens_reported"]["relative_change_percent"], -70)

    def test_failed_resume_preserves_known_usage_and_marks_lower_bound(self):
        result = self.report([{"type":"thread.started", "thread_id":"a"}, self.turn(),
                              {"type":"thread.started", "thread_id":"a"},
                              {"type":"turn.failed"}])
        self.assertEqual(result["totals"]["input_tokens_reported"], 1000)
        self.assertEqual(result["totals"]["output_tokens_reported"], 100)
        self.assertEqual(result["totals"]["failed_samples"], 1)
        self.assertEqual(result["totals"]["samples_with_partial_usage"], 1)
        compared = usage.compare(self.report([self.turn()]), result)
        self.assertIsNone(compared["observed_changes"]["input_tokens_reported"]["difference"])

    def test_success_after_failure_replaces_lower_bound_without_double_counting(self):
        result = self.report([self.turn(), {"type":"turn.started"}, {"type":"turn.failed"},
                              {"type":"turn.started"}, self.turn(input=1500)])
        self.assertEqual(result["totals"]["input_tokens_reported"], 1500)
        self.assertEqual(result["totals"]["samples_with_partial_usage"], 0)
        self.assertEqual(result["totals"]["failed_samples"], 1)

    def test_failure_does_not_reset_native_monotonicity_check(self):
        with self.assertRaisesRegex(ValueError, "decreased"):
            self.report([self.turn(), {"type":"turn.started"}, {"type":"turn.failed"},
                         {"type":"turn.started"}, self.turn(input=900)])

    def test_missing_measurements_produce_unknown_token_deltas(self):
        for format_name in ("codex-exec", "opencodex"):
            measured = self.report([self.turn()] if format_name == "codex-exec" else [self.request()], format_name)
            missing = self.report([{"type":"turn.failed"}] if format_name == "codex-exec" else
                                  [self.request(usage=None, usageStatus="unreported", status=502)], format_name)
            for before, after in ((measured, missing), (missing, measured), (missing, missing)):
                with self.subTest(format=format_name, before=before["totals"]["samples_with_usage"], after=after["totals"]["samples_with_usage"]):
                    changes = usage.compare(before, after)["observed_changes"]
                    for key in ("input_tokens_reported", "output_tokens_reported", "fresh_input_tokens_reported"):
                        self.assertIsNone(changes[key]["difference"])
                        self.assertIsNone(changes[key]["relative_change_percent"])

    def test_measured_zero_remains_a_known_difference(self):
        before = self.report([self.turn()])
        after = self.report([self.turn(input=0, cached=0, output=0, reasoning=0)])
        change = usage.compare(before, after)["observed_changes"]["input_tokens_reported"]
        self.assertEqual(change["difference"], -1000)
        self.assertEqual(change["relative_change_percent"], -100)

    def test_model_distribution_warning_handles_proportions_and_membership(self):
        def reports(models):
            return self.report([self.request(str(i), requestedModel=model, requestedEffort="medium")
                                for i, model in enumerate(models)], "opencodex")
        astra, sol = "gpt-6-astra", "gpt-5.6-sol"
        cases = [([astra]*9+[sol], [astra]+[sol]*9, True),
                 ([astra, sol], [astra, sol]*2, False), ([astra], [sol], True)]
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                notes = usage.compare(reports(before), reports(after))["notes"]
                self.assertEqual(any("sample mix differs" in note for note in notes), expected)

    def test_effort_distribution_warning_handles_equal_size_changed_mix(self):
        def reports(efforts):
            return self.report([self.request(str(i), requestedEffort=effort)
                                for i, effort in enumerate(efforts)], "opencodex")
        notes = usage.compare(reports(["low"]*9+["high"]), reports(["low"]+["high"]*9))["notes"]
        self.assertTrue(any("sample mix differs" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
