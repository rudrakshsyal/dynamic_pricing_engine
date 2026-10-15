import unittest
import pandas as pd
from src.synthetic_benchmark import (
    DirectForecast,
    validate_direct,
    VALIDATION,
    TEST,
    HORIZONS,
    make_pilot_agent,
    direct_request,
)
from src.research_experiments import Recipe, TARGETS
from unittest.mock import patch


class SyntheticBenchmarkTests(unittest.TestCase):
    def payload(self):
        return {
            **{c: [0.1 if c.endswith("_rate") else 10] * 90 for c in TARGETS},
            "quote_multiplier": [1.0] * 17,
            "conversion_probability": [0.05] * 17,
        }

    def test_forecast_schema_and_alignment(self):
        dates = pd.date_range("2033-01-01", periods=90)
        frame, curve = validate_direct(self.payload(), dates)
        self.assertEqual(frame.index.tolist(), dates.tolist())
        self.assertEqual(len(curve["x"]), 17)
        self.assertEqual(len(DirectForecast.model_json_schema()["required"]), 9)

    def test_rejects_bad_predictions(self):
        for mutation in ["length", "rate", "nan", "curve"]:
            p = self.payload()
            if mutation == "length":
                p["aog_rate"] = p["aog_rate"][:-1]
            if mutation == "rate":
                p["aog_rate"][0] = 1.1
            if mutation == "nan":
                p["aog_rate"][0] = float("nan")
            if mutation == "curve":
                p["quote_multiplier"] = [0] * 17
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_direct(p, pd.date_range("2033-01-01", periods=90))

    def test_long_history_enabled(self):
        self.assertEqual(Recipe(family="ridge", train_days=3000).train_days, 3000)
        with self.assertRaises(ValueError):
            Recipe(family="ridge", train_days=4000)

    def test_temporal_separation(self):
        self.assertLess(
            max(pd.Timestamp(o) + pd.Timedelta(days=90) for o in VALIDATION),
            pd.Timestamp(TEST[0]) + pd.Timedelta(days=1),
        )
        self.assertEqual(HORIZONS, [14, 28, 90])

    def test_agent_tools_hide_final_evaluation(self):
        agent = make_pilot_agent(None)
        self.assertNotIn("score", {t.name for t in agent.tools})
        self.assertEqual(len(agent.tools), 6)

    def test_direct_request_contains_only_supplied_train_history(self):
        train = pd.DataFrame(
            {c: [0.123456, 2] for c in TARGETS},
            index=pd.date_range("2030-01-01", periods=2),
        )
        qc = pd.Series([2, 1, 1], index=[7000, 10000, 15000])
        cv = pd.DataFrame(
            {"mean": [0.1, 0.05, 0.01], "size": [10, 10, 10]}, index=qc.index
        )
        with patch("src.synthetic_benchmark.curve_bins", return_value=(qc, cv)):
            r = direct_request(train, pd.date_range("2030-01-03", periods=90), None)
        self.assertEqual(len(r["daily_rows"]), 2)
        self.assertEqual(r["history_end"], "2030-01-02")
        self.assertEqual(r["daily_rows"][0][0], 0.1235)


if __name__ == "__main__":
    unittest.main()
