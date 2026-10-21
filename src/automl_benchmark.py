"""Offline fixed-grid AutoML baseline; no model-provider calls."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
import time
import pandas as pd
from src.model_benchmark import TARGETS, write_json
from src.model_selection import CURVES
from src.research_experiments import Workbench
from src.synthetic_benchmark import load, hashes, VALIDATION
from src.synthetic_robustness import (
    run as transfer,
    summarize,
    PATHS,
    ORIGINS,
    HORIZONS,
)

RECIPES = [
    {"family": "current"},
    {"family": "seasonal_naive", "train_days": 1095},
    {"family": "ridge", "train_days": 1095, "alpha": 10},
    {
        "family": "extra_trees",
        "train_days": 1095,
        "trees": 150,
        "depth": 4,
        "min_leaf": 7,
    },
]


def choose(rows):
    valid = [r for r in rows if r["status"] == "ok"]
    if not valid:
        raise ValueError("No successful candidates")
    # Stable input order breaks exact ties in favor of the baseline.
    return min(valid, key=lambda r: r["score"])


def main(root, out, previous):
    if out.exists():
        raise ValueError("Fresh output directory required")
    start = time.monotonic()
    out.mkdir(parents=True)
    plan = {
        "strategy": "fixed-grid component selection",
        "recipes": RECIPES,
        "curves": CURVES,
        "validation_origins": VALIDATION,
        "horizon": 90,
        "test_origins": ORIGINS,
        "paths": PATHS,
        "trials": 34,
        "agent_trials": 20,
        "objective": "Component pooled RMSE; multiplier bin MAE; conversion log loss. Lowest validation score wins; ties keep earlier recipe.",
        "warning": "Retrospective benchmark on already inspected test scenarios; unequal search spaces/budgets; not causal proof of search superiority.",
        "source_hashes": {p: hashes(root / p) for p in PATHS},
        "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "api_calls": 0,
    }
    write_json(out / "plan.json", plan)
    daily, q = load(root / "baseline_seed42")
    w = Workbench(
        daily, q, out / "selection", max_trials=34, origins=VALIDATION, horizon=90
    )
    w.plan("Fixed grid and minimum component validation loss; no test-driven tuning.")
    choices = {}
    for c in TARGETS + list(CURVES):
        configs = (
            RECIPES
            if c in TARGETS
            else [{"family": "curve", "curve_name": n} for n in CURVES[c]]
        )
        rows = [w.trial(c, config, "Predeclared fixed grid") for config in configs]
        winner = choose(rows)
        choices[c] = {
            "trial_id": winner["id"],
            "reason": "Minimum validation loss; fixed order breaks exact ties.",
        }
        print(c, winner["recipe"], flush=True)
    w.freeze(choices)
    transfer(root, out / "selection", out / "evaluation")
    # Reuse unchanged baseline and original agent rows from the previously saved run.
    old_records = json.loads((previous / "fold_results.json").read_text())
    new_records = json.loads((out / "evaluation/fold_results.json").read_text())
    added = [
        {**r, "candidate": "automl"}
        for r in new_records
        if r["candidate"] == "frozen_agent"
    ]
    old_prices = pd.read_csv(previous / "pricing.csv")
    new_prices = pd.read_csv(out / "evaluation/pricing.csv")
    new_prices = new_prices[new_prices.candidate == "frozen_agent"].copy()
    new_prices["candidate"] = "automl"
    # Guard comparability by verifying common current predictions reproduce prior metrics.
    old_lookup = {
        (r["path"], r["origin"], r["horizon"]): r
        for r in old_records
        if r["candidate"] == "current"
    }
    import numpy as np

    for r in new_records:
        if r["candidate"] == "current":
            prior = old_lookup[(r["path"], r["origin"], r["horizon"])]
            for c in r["forecast_errors"]:
                if not np.isclose(
                    r["forecast_errors"][c]["rmse"],
                    prior["forecast_errors"][c]["rmse"],
                    rtol=1e-5,
                    atol=1e-7,
                ):
                    raise ValueError(
                        "Recomputed baseline differs from saved comparison"
                    )
    prices = pd.concat([old_prices, new_prices], ignore_index=True)
    aggregate = summarize(old_records + added, prices)
    prices.to_csv(out / "comparison_pricing.csv", index=False)
    write_json(out / "comparison_results.json", aggregate)
    write_json(
        out / "status.json",
        {
            "status": "complete",
            "api_calls": 0,
            "api_cost_usd": 0,
            "wall_seconds": time.monotonic() - start,
            "successful_trials": sum(r["status"] == "ok" for r in w.trials.values()),
            "total_trials": len(w.trials),
        },
    )
    # The generic transfer runner calls its challenger frozen_agent: clarify that artifact.
    (out / "evaluation/REPORT.md").write_text(
        "# AutoML transfer artifacts\n\nIn this subdirectory only, `frozen_agent` is the generic runner label for the frozen AutoML selection, NOT a newly run LLM agent. Use ../comparison_results.json for correctly labeled three-way results.\n"
    )
    lines = [
        "# AutoML comparison",
        "",
        "90-day supply RMSE; lower is better. Fixed-grid AutoML: 34 trials. Earlier GPT-directed selection: 20 trials. Zero new API calls.",
        "",
        "| Scenario | Current | Agent | AutoML | AutoML vs current |",
        "|---|---:|---:|---:|---:|",
    ]
    for p in PATHS:
        rows = {
            r["candidate"]: r
            for r in aggregate
            if r["path"] == p and r["horizon"] == 90
        }
        v = [
            rows[n]["forecast_errors"]["remaining_supply_proxy"]["rmse"]
            for n in ["current", "frozen_agent", "automl"]
        ]
        lines.append(
            f"| {p} | {v[0]:.3f} | {v[1]:.3f} | {v[2]:.3f} | {v[2] / v[0] - 1:+.1%} |"
        )
    lines += [
        "",
        "Price errors in comparison_results.json use a newly calculated common non-DNQ date intersection across all THREE candidates; do not compare directly with older two-way price MAEs.",
        "",
        plan["warning"],
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("experiments/synthetic_fleet_v1"))
    p.add_argument("--out", type=Path, default=Path("experiments/automl_grid_v1"))
    p.add_argument(
        "--previous", type=Path, default=Path("experiments/synthetic_robustness_v1")
    )
    a = p.parse_args()
    main(a.root, a.out, a.previous)
