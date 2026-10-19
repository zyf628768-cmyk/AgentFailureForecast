import copy
from datetime import datetime, timedelta, timezone
import unittest

from agent_failure_forecast.backtest import backtest
from agent_failure_forecast.features import extract
from agent_failure_forecast.predictor import evaluate, predict, validate_history, sigmoid, fit, score, brier


def synthetic_history(n=240):
    """Deterministic, deliberately separable synthetic data: NOT production evidence."""
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        dangerous = bool(i % 2)
        rows.append({"task_id": f"synthetic-{i}", "started_at": (start+timedelta(hours=i*2)).isoformat(),
                     "finished_at": (start+timedelta(hours=i*2+1)).isoformat(), "failed": dangerous,
                     "plan_recorded_at": (start+timedelta(hours=i*2)).isoformat(),
                     "outcome_recorded_at": (start+timedelta(hours=i*2+1)).isoformat(),
                     "plan": {"goal": "Synthetic test", "acceptance": ["Result recorded"],
                              "steps": [{"id": "one", "description": "deploy production" if dangerous else "inspect local configuration"}]},
                     "tools_used": [], "failure_type": "synthetic_only" if dangerous else ""})
    return rows


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = synthetic_history()
        cls.metrics, cls.model = evaluate(cls.rows)

    def test_no_history(self):
        result = predict({}, [])
        self.assertEqual(result["mode"], "rules")
        self.assertIsNone(result["failure_probability"])

    def test_small_history(self):
        result, model = evaluate(self.rows[:30])
        self.assertEqual(result["reason"], "insufficient_history")
        self.assertIsNone(model)

    def test_statistical_mode(self):
        self.assertTrue(self.metrics["eligible"])
        result = predict(self.rows[1]["plan"], self.rows, "2026-01-01T00:00:00Z")
        self.assertEqual(result["mode"], "statistical")
        self.assertGreater(result["failure_probability"], 0)
        self.assertLess(result["failure_probability"], 1)

    def test_temporal_splits(self):
        m = self.metrics
        self.assertEqual(m["split_samples"], {"train": 120, "calibration": 48, "selection": 36, "test": 36})
        self.assertLess(m["boundaries"]["train_end"], m["boundaries"]["calibration_start"])
        self.assertLess(m["boundaries"]["calibration_end"], m["boundaries"]["test_start"])
        self.assertLess(m["boundaries"]["calibration_end"], m["boundaries"]["selection_start"])
        self.assertLess(m["boundaries"]["selection_end"], m["boundaries"]["test_start"])

    def test_baseline_comparison(self):
        q = self.metrics["quality"]
        self.assertLess(q["calibrated_brier"], q["baseline_brier"])
        self.assertAlmostEqual(q["baseline_brier"], 0.25)

    def test_calibration_is_fitted_separately(self):
        w, c = self.model
        self.assertEqual(len(c), 2)
        q = self.metrics["quality"]
        self.assertNotEqual(q["raw_brier"], q["calibrated_brier"])
        self.assertEqual(sum(b["count"] for b in q["calibration_bins"]), 36)

    def test_test_labels_do_not_change_fitting(self):
        changed = copy.deepcopy(self.rows)
        for r in changed[204:]:
            r["failed"] = not r["failed"]
        metrics, model = evaluate(changed)
        self.assertEqual(model, self.model)
        self.assertEqual(metrics["eligible"], self.metrics["eligible"])
        self.assertNotEqual(metrics["quality"], self.metrics["quality"])

    def test_one_class_fallback(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            r["failed"] = False
        self.assertEqual(evaluate(rows)[0]["reason"], "insufficient_class_support")

    def test_overlap_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["finished_at"] = rows[-1]["finished_at"]
        rows[0]["outcome_recorded_at"] = rows[-1]["outcome_recorded_at"]
        self.assertEqual(evaluate(rows)[0]["reason"], "overlapping_time_blocks")

    def test_as_of_prevents_future_leak(self):
        result = predict({}, self.rows, self.rows[50]["started_at"])
        self.assertEqual(result["excluded_future_records"], 190)
        self.assertIsNone(result["failure_probability"])

    def test_timestamp_sort(self):
        self.assertEqual(validate_history(list(reversed(self.rows))), self.rows)

    def test_duplicate_tasks(self):
        with self.assertRaises(ValueError):
            validate_history([self.rows[0], self.rows[0]])

    def test_malformed_history(self):
        for key, value in [("failed", 1), ("started_at", "2025-01-01"), ("finished_at", "2024-01-01T00:00:00Z"), ("plan", None)]:
            row = copy.deepcopy(self.rows[0])
            row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_history([row])

    def test_outcome_metadata_not_features(self):
        row = copy.deepcopy(self.rows[0])
        before = extract(row["plan"])
        row.update(failed=True, tools_used=["dangerous"], failure_type="failure")
        self.assertEqual(before, extract(row["plan"]))

    def test_expanding_backtest(self):
        result = backtest(self.rows)
        self.assertEqual(len(result["folds"]), 3)
        self.assertEqual([m["samples"] for m in result["folds"]], [144, 192, 240])
        self.assertTrue(all("quality" in m for m in result["folds"]))

    def test_small_backtest_fallback(self):
        self.assertTrue(all(not m["eligible"] for m in backtest(self.rows[:10])["folds"]))

    def test_no_signal_baseline_gate(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            r["plan"] = self.rows[0]["plan"]
        self.assertFalse(evaluate(rows)[0]["eligible"])

    def test_numeric_stability(self):
        self.assertTrue(0 < sigmoid(-10000) < 1)
        self.assertTrue(0 < sigmoid(10000) < 1)


if __name__ == "__main__":
    unittest.main()
