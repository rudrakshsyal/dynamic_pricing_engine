"""Offline transfer test of frozen agent recipes; never invokes an LLM."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd
from src.synthetic_benchmark import load, split, hashes, HORIZONS
from src.model_benchmark import (
    TARGETS,
    baseline,
    constrain,
    fit_curves,
    evaluate,
    write_json,
)
from src.model_selection import CURVES, curve_candidate, combine
from src.research_experiments import Recipe, predict_recipe

PATHS = [
    "baseline_seed42",
    "baseline_seed123",
    "baseline_seed2026",
    "demand_shift_seed42",
    "maintenance_stress_seed42",
]
ORIGINS = [str(d.date()) for d in pd.date_range("2032-12-31", "2035-09-30", freq="QE")]


def summarize(records, prices):
    output = []
    for (path, horizon), group in prices.groupby(["path", "horizon"]):
        common = None
        for _, frame in group.groupby("candidate"):
            valid = frame[frame["yield"].notna() & frame.reference_yield.notna()]
            keys = set(zip(valid.origin, valid.date))
            common = keys if common is None else common & keys
        for name, frame in group.groupby("candidate"):
            rs = [
                r
                for r in records
                if (r["path"], r["horizon"], r["candidate"]) == (path, horizon, name)
            ]
            errors = {}
            for c in TARGETS + ["remaining_supply_proxy"]:
                ms = [r["forecast_errors"][c] for r in rs]
                n = sum(m["n"] for m in ms)
                errors[c] = {
                    "n": n,
                    "rmse": float(
                        np.sqrt(sum(m["n"] * m["rmse"] ** 2 for m in ms) / n)
                    ),
                    "mae": sum(m["n"] * m["mae"] for m in ms) / n,
                }
            paired = frame[[k in common for k in zip(frame.origin, frame.date)]]
            output.append(
                {
                    "path": path,
                    "horizon": int(horizon),
                    "candidate": name,
                    "forecast_errors": errors,
                    "common_price_n": len(paired),
                    "common_price_mae": float(
                        abs(paired["yield"] - paired.reference_yield).mean()
                    )
                    if len(paired)
                    else None,
                    "dnq_disagreement": float(
                        (
                            (frame.status == "DNQ_zero_supply")
                            != (frame.reference_status == "DNQ_zero_supply")
                        ).mean()
                    ),
                }
            )
    return output


def run(root, frozen, out):
    if out.exists():
        raise ValueError("Use a fresh output directory; results are not overwritten")
    choices = json.loads((frozen / "frozen_choices.json").read_text())
    trials = json.loads((frozen / "trials.json").read_text())
    recipes = {c: trials[choices[c]["trial_id"]]["recipe"] for c in choices}
    if any(trials[choices[c]["trial_id"]]["kind"] != "model" for c in TARGETS):
        raise ValueError("This transfer runner requires frozen single-model recipes")
    out.mkdir(parents=True)
    write_json(
        out / "plan.json",
        {
            "paths": PATHS,
            "origins": ORIGINS,
            "horizons": HORIZONS,
            "primary_horizon": 90,
            "api_calls": 0,
            "api_cost_usd": 0,
            "protocol": "Expanding training through each origin; fixed recipes, no reselection. Quarterly tests include June/July maintenance shocks. Short horizons are prefixes.",
            "recipes": recipes,
            "frozen_hashes": {
                f: sha256((frozen / f).read_bytes()).hexdigest()
                for f in ["trials.json", "frozen_choices.json"]
            },
            "source_hashes": {p: hashes(root / p) for p in PATHS},
            "code_hash": sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    )
    records, prices, predictions = [], [], []
    for path in PATHS:
        daily, quotes = load(root / path)
        for origin in ORIGINS:
            train, actual, mature = split(daily, quotes, origin)
            current = constrain(baseline(train, actual.index))
            agent = current.copy()
            for c in TARGETS:
                recipe = Recipe.model_validate(recipes[c])
                if recipe.family != "current":
                    agent[c] = predict_recipe(train, actual.index, c, recipe)
            ref = fit_curves(mature)
            curves = {
                c: curve_candidate(mature, c, recipes[c]["curve_name"], ref)
                for c in CURVES
            }
            agent_curve = combine(curves["quote_multiplier"], curves["conversion"])
            for name, pred, curve in [
                ("current", current, ref),
                ("frozen_agent", agent, agent_curve),
            ]:
                for date in actual.index:
                    predictions.append(
                        {
                            "path": path,
                            "origin": origin,
                            "date": str(date.date()),
                            "candidate": name,
                            **{
                                f"actual_{c}": float(actual.loc[date, c])
                                for c in TARGETS
                            },
                            **{
                                f"predicted_{c}": float(pred.loc[date, c])
                                for c in TARGETS
                            },
                        }
                    )
                for horizon in HORIZONS:
                    act = actual.iloc[:horizon]
                    held = quotes[
                        (quotes.quote_date > pd.Timestamp(origin))
                        & (quotes.quote_date <= act.index[-1])
                        & (quotes.dep_date <= act.index[-1])
                    ]
                    result, rows = evaluate(
                        name,
                        pred.iloc[:horizon],
                        act,
                        curve,
                        ref,
                        float(train.num_tails.iloc[-1]),
                        held,
                    )
                    meta = {"path": path, "origin": origin, "horizon": horizon}
                    records.append({**meta, "candidate": name, **result})
                    prices.extend([{**meta, **r} for r in rows])
            print(f"Completed {path}: {origin}", flush=True)
        write_json(out / "fold_results.json", records)
        pd.DataFrame(predictions).to_csv(out / "predictions.csv", index=False)
        pd.DataFrame(prices).to_csv(out / "pricing.csv", index=False)
    aggregate = summarize(records, pd.DataFrame(prices))
    write_json(out / "aggregate_results.json", aggregate)
    write_json(
        out / "status.json",
        {
            "status": "complete",
            "api_calls": 0,
            "api_cost_usd": 0,
            "folds": len(PATHS) * len(ORIGINS),
        },
    )
    lines = [
        "# Frozen-agent robustness results",
        "",
        "Offline only: 0 API calls, $0 API cost. Lower errors are better.",
        "",
        "| Path | Horizon | Current supply RMSE | Frozen agent RMSE | Change | Current price MAE | Agent price MAE | Common dates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for path in PATHS:
        for h in HORIZONS:
            pair = {
                r["candidate"]: r
                for r in aggregate
                if r["path"] == path and r["horizon"] == h
            }
            a, b = pair["current"], pair["frozen_agent"]
            x, y = [
                r["forecast_errors"]["remaining_supply_proxy"]["rmse"] for r in [a, b]
            ]
            lines.append(
                f"| {path} | {h} | {x:.3f} | {y:.3f} | {(y / x - 1):+.1%} | {a['common_price_mae']:.2f} | {b['common_price_mae']:.2f} | {a['common_price_n']} |"
            )
    lines += [
        "",
        "Price MAE is deviation from a diagnostic reference using realized components and training-only current curves, not an observed optimal price or revenue. It favors the current curve construction by design. Common non-DNQ dates match between candidates within each path/horizon, not necessarily across paths.",
        "",
        "Twelve quarterly origins per path, 2032-12-31 through 2035-09-30; 90 days each (1,080 days per path). The 14/28-day scores are overlapping prefixes, not additional independent tests. Models refit using only observations available at each origin. Ridge uses its frozen 1,095-day window; current recipes use all prior history.",
        "",
        "Agent choices were selected previously on baseline seed42 validation windows in 2032. This measures transfer of those fixed choices, not a newly adapting agent. Three baseline seeds and two paired seed42 stress scenarios are related simulations calibrated from the same two real years. No confidence or real-world revenue claim is established. No fresh real data are available; Gemini remains untested.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--frozen", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.frozen, a.out)
