import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.research_experiments import (
    Workbench,
    Recipe,
    COMPONENTS,
    TARGETS,
    CURVES,
    predict_recipe,
    feature_row,
)
from src.research_agent import make_agent, run_research, final_evaluation


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        dates = pd.date_range("2024-01-01", "2025-11-30")
        self.daily = pd.DataFrame(
            {
                c: np.full(len(dates), 0.05 if c.endswith("_rate") else 10.0)
                for c in TARGETS
            },
            index=dates,
        )
        self.daily["num_tails"] = 43
        self.quotes = pd.DataFrame(
            {
                "quote_date": pd.to_datetime(["2024-01-01", "2025-11-01"]),
                "dep_date": pd.to_datetime(["2024-01-02", "2025-11-02"]),
            }
        )
        self.quotes["final_yield"] = 10000.0
        self.quotes["yield_per_eft"] = 10000.0
        self.quotes["booked"] = 0
        self.w = Workbench(self.daily, self.quotes, self.tmp.name)
        self.w.plan("Compare models using fold stability.")

    def trial(self, family="rolling_mean", **kw):
        return self.w.trial(TARGETS[0], {"family": family, **kw}, "Test hypothesis")

    def seed(self):
        choices = {}
        for c in COMPONENTS:
            config = (
                {"family": "current"}
                if c in TARGETS
                else {"family": "curve", "curve_name": CURVES[c][0]}
            )
            self.w.trials[c] = {
                "id": c,
                "component": c,
                "status": "ok",
                "kind": "model",
                "recipe": Recipe(**config).model_dump(),
                "score": 1,
            }
            choices[c] = {"trial_id": c, "reason": "Retain baseline"}
        return choices

    def test_holdout_not_in_tools(self):
        self.assertLess(self.w.daily.index.max(), pd.Timestamp("2025-11-01"))
        self.assertLess(self.w.quotes.quote_date.max(), pd.Timestamp("2025-11-01"))
        self.assertEqual(self.w.inspect(TARGETS[0])["through"], "2025-06-30")

    def test_recipe_bounds(self):
        for cfg in [
            {"family": "shell"},
            {"family": "ridge", "lags": [0]},
            {"family": "ridge", "lags": [7, 7]},
            {"family": "xgboost", "trees": 10000},
            {"family": "ridge", "path": "/tmp/x"},
        ]:
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                Recipe.model_validate(cfg)

    def test_features(self):
        self.assertEqual(
            feature_row(
                range(28),
                pd.Timestamp("2025-01-01"),
                Recipe(family="ridge", lags=[1, 7], windows=[7], calendar=False),
            )[:3],
            [27, 21, 24],
        )

    def test_forecast_families(self):
        train = self.daily.loc[:"2024-12-31"]
        dates = pd.date_range("2025-01-01", periods=5)
        for family in [
            "rolling_mean",
            "seasonal_naive",
            "ridge",
            "extra_trees",
            "xgboost",
            "prophet",
        ]:
            with self.subTest(family=family):
                v = predict_recipe(
                    train,
                    dates,
                    TARGETS[0],
                    Recipe(family=family, trees=20, log_transform=True),
                )
                self.assertEqual(len(v), 5)
                self.assertTrue(np.isfinite(v).all())
                self.assertTrue(((v >= 0) & (v <= 1)).all())

    def test_budget_and_cache(self):
        self.w.max_trials = 1
        r = self.trial()
        self.assertEqual(self.trial()["id"], r["id"])
        with self.assertRaises(ValueError):
            self.trial(mean_window=14)
        self.assertEqual(self.w.used, 1)

    def test_failed_trial_counted(self):
        with patch(
            "src.research_experiments.predict_recipe", side_effect=RuntimeError("test")
        ):
            self.assertEqual(self.trial()["status"], "failed")
        self.assertEqual(self.w.used, 1)

    def test_ensemble(self):
        a = self.trial()
        b = self.trial("ridge")
        r = self.w.ensemble([a["id"], b["id"]], [0.3, 0.7], "Stability")
        self.assertLess(r["score"], 1e-10)
        self.assertIn("weekday_bias", self.w.review(r["id"]))
        with self.assertRaises(ValueError):
            self.w.ensemble([a["id"], b["id"]], [1, 1], "Bad weights")

    def test_freeze(self):
        with self.assertRaises(ValueError):
            self.w.freeze({})
        choices = self.seed()
        self.w.freeze(choices)
        choices[TARGETS[0]]["reason"] = "mutated"
        self.assertNotEqual(self.w.frozen[TARGETS[0]]["reason"], "mutated")
        with self.assertRaises(ValueError):
            self.trial()

    def test_agent_can_choose_non_minimum(self):
        choices = self.seed()
        self.w.trials["better"] = {
            **self.w.trials[TARGETS[0]],
            "id": "better",
            "score": 0.01,
        }
        self.w.freeze(choices)
        self.assertEqual(self.w.frozen[TARGETS[0]]["trial_id"], TARGETS[0])

    def test_sdk_and_mocked_run(self):
        agent = make_agent(self.w)
        self.assertEqual(len(agent.tools), 7)
        self.assertFalse(agent.model_settings.parallel_tool_calls)
        self.assertNotIn("final_evaluation", {t.name for t in agent.tools})

        async def fake(*args, **kwargs):
            self.w.freeze(self.seed())
            return SimpleNamespace(
                final_output=SimpleNamespace(
                    model_dump=lambda: {"methodology": "Synthetic", "caveats": []}
                )
            )

        asyncio.run(run_research(self.w, "gpt-5.5", 10, 1000, runner=fake))
        self.assertEqual(
            json.loads((Path(self.tmp.name) / "run_status.json").read_text())["status"],
            "frozen",
        )

    def test_incomplete_run(self):
        async def fake(*args, **kwargs):
            return SimpleNamespace()

        with self.assertRaises(RuntimeError):
            asyncio.run(run_research(self.w, "gpt-5.5", 10, 1000, runner=fake))
        self.assertFalse((Path(self.tmp.name) / "final_results.json").exists())

    def test_final_gate(self):
        with self.assertRaises(ValueError):
            final_evaluation(self.w, Path("/not-read"))

    def test_sdk_tool_dispatch(self):
        from agents.tool_context import ToolContext

        agent = make_agent(self.w)
        tool = next(t for t in agent.tools if t.name == "run_trial")
        args = json.dumps(
            {
                "component": TARGETS[0],
                "recipe": Recipe(family="rolling_mean").model_dump(),
                "rationale": "SDK dispatch smoke test",
            }
        )
        ctx = ToolContext(
            context=None,
            tool_name=tool.name,
            tool_call_id="synthetic",
            tool_arguments=args,
        )
        result = asyncio.run(tool.on_invoke_tool(ctx, args))
        self.assertEqual(json.loads(result)["status"], "ok")

    def test_cli_requires_approval_without_reading_key(self):
        import subprocess, sys

        result = subprocess.run(
            [sys.executable, "-m", "src.research_agent", "--out", self.tmp.name],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit --allow-paid required", result.stderr)

    def test_final_report(self):
        self.w.freeze(self.seed())
        curve = {"x": [7000, 15000], "multiplier": [1, 1], "a": 0.1, "b": 0.1}
        with (
            patch("src.research_agent.load_daily", return_value=self.daily),
            patch(
                "src.research_agent.pd.read_parquet", return_value=self.quotes.copy()
            ),
            patch("src.research_agent.fit_curves", return_value=curve),
            patch(
                "src.research_agent.curve_candidate", side_effect=lambda q, c, n, r: r
            ),
            patch(
                "src.research_agent.baseline",
                side_effect=lambda t, d: self.daily.reindex(d)[TARGETS],
            ),
            patch(
                "src.research_agent.selected_prediction",
                side_effect=lambda w, t, train, d: self.daily.reindex(d)[t].to_numpy(),
            ),
        ):
            results = final_evaluation(self.w, Path("/synthetic"))
        self.assertEqual(
            results["agent_full"]["forecast_errors"][TARGETS[0]]["rmse"], 0
        )
        self.assertTrue((Path(self.tmp.name) / "report.md").exists())


if __name__ == "__main__":
    unittest.main()
