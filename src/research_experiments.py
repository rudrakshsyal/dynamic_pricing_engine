"""Adaptive validation workbench. No API calls and no final-test access in tools."""

from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.model_benchmark import TARGETS, baseline, constrain, metrics, write_json
from src.model_selection import CURVES, curve_candidate, curve_score, fit_curves

COMPONENTS = TARGETS + list(CURVES)
ORIGINS = ["2025-06-30", "2025-08-31", "2025-09-30"]
HORIZON = 28
FINAL_ORIGIN = (
    "2025-10-31"  # Explicitly retrospective: already inspected in prior experiments.
)


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: Literal[
        "current",
        "seasonal_naive",
        "rolling_mean",
        "ridge",
        "extra_trees",
        "xgboost",
        "prophet",
        "curve",
    ]
    lags: list[int] = Field(
        default_factory=lambda: [1, 7, 14, 28], min_length=1, max_length=8
    )
    windows: list[int] = Field(
        default_factory=lambda: [7, 28], min_length=1, max_length=4
    )
    calendar: bool = True
    log_transform: bool = False
    train_days: int = Field(default=730, ge=180, le=730)
    mean_window: int = Field(default=28, ge=7, le=90)
    alpha: float = Field(default=10, ge=0.01, le=1000)
    trees: int = Field(default=150, ge=20, le=300)
    depth: int = Field(default=4, ge=1, le=8)
    min_leaf: int = Field(default=7, ge=2, le=30)
    learning_rate: float = Field(default=0.04, ge=0.01, le=0.3)
    changepoint_scale: float = Field(default=0.05, ge=0.001, le=0.5)
    seasonality_mode: Literal["additive", "multiplicative"] = "additive"
    weekly: bool = True
    yearly: bool = True
    curve_name: str = ""

    @model_validator(mode="after")
    def check_lags(self):
        for values in (self.lags, self.windows):
            if len(set(values)) != len(values) or any(v < 1 or v > 90 for v in values):
                raise ValueError("Unique lags/windows between 1 and 90 required")
        return self


def feature_row(history, day, recipe):
    a = np.asarray(history, float)
    if len(a) < max(recipe.lags + recipe.windows):
        raise ValueError("Insufficient lag history")
    row = [a[-v] for v in recipe.lags]
    for w in recipe.windows:
        row.extend([a[-w:].mean(), a[-w:].std()])
    if recipe.calendar:
        row.extend(
            [
                np.sin(2 * np.pi * day.dayofweek / 7),
                np.cos(2 * np.pi * day.dayofweek / 7),
                np.sin(2 * np.pi * day.dayofyear / 365.25),
                np.cos(2 * np.pi * day.dayofyear / 365.25),
            ]
        )
    return row


def predict_recipe(train, dates, component, recipe):
    if recipe.family == "current":
        return constrain(baseline(train, dates))[component].to_numpy()
    y = train[component].iloc[-recipe.train_days :]
    upper = 1 if component.endswith("_rate") else np.inf
    if recipe.family == "seasonal_naive":
        pred = np.resize(y.iloc[-7:].to_numpy(), len(dates))
    elif recipe.family == "rolling_mean":
        pred = np.repeat(y.iloc[-recipe.mean_window :].mean(), len(dates))
    elif recipe.family == "prophet":
        from prophet import Prophet

        m = Prophet(
            weekly_seasonality=recipe.weekly,
            yearly_seasonality=recipe.yearly,
            daily_seasonality=False,
            changepoint_prior_scale=recipe.changepoint_scale,
            seasonality_mode=recipe.seasonality_mode,
            uncertainty_samples=0,
        )
        m.fit(
            pd.DataFrame(
                {
                    "ds": y.index,
                    "y": np.log1p(y.values) if recipe.log_transform else y.values,
                }
            )
        )
        pred = m.predict(pd.DataFrame({"ds": dates})).yhat.to_numpy()
        if recipe.log_transform:
            pred = np.expm1(pred)
    else:
        values = np.log1p(y.values) if recipe.log_transform else y.values
        start = max(recipe.lags + recipe.windows)
        x = np.asarray(
            [feature_row(values[:i], y.index[i], recipe) for i in range(start, len(y))]
        )
        labels = values[start:]
        if recipe.family == "ridge":
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.linear_model import Ridge

            m = make_pipeline(StandardScaler(), Ridge(alpha=recipe.alpha))
            m.fit(x, labels)
            predict = lambda row: float(m.predict(np.asarray([row]))[0])
        elif recipe.family == "extra_trees":
            from sklearn.ensemble import ExtraTreesRegressor

            m = ExtraTreesRegressor(
                n_estimators=recipe.trees,
                max_depth=recipe.depth,
                min_samples_leaf=recipe.min_leaf,
                random_state=42,
                n_jobs=2,
            )
            m.fit(x, labels)
            predict = lambda row: float(m.predict(np.asarray([row]))[0])
        elif recipe.family == "xgboost":
            import xgboost as xgb

            m = xgb.train(
                {
                    "objective": "reg:squarederror",
                    "max_depth": recipe.depth,
                    "eta": recipe.learning_rate,
                    "min_child_weight": recipe.min_leaf,
                    "seed": 42,
                    "nthread": 2,
                    "tree_method": "hist",
                },
                xgb.DMatrix(x, label=labels),
                num_boost_round=recipe.trees,
            )
            predict = lambda row: float(m.predict(xgb.DMatrix(np.asarray([row])))[0])
        else:
            raise ValueError("Not a forecast recipe")
        history = values.tolist()
        pred = []
        for day in dates:
            raw = predict(feature_row(history, day, recipe))
            v = float(np.clip(np.expm1(raw) if recipe.log_transform else raw, 0, upper))
            if not np.isfinite(v):
                raise ValueError("Nonfinite prediction")
            pred.append(v)
            history.append(float(np.log1p(v)) if recipe.log_transform else v)
    pred = np.clip(pred, 0, upper)
    if not np.isfinite(pred).all():
        raise ValueError("Nonfinite predictions")
    return np.asarray(pred)


class Workbench:
    """Receives development data only; cannot read files or final-test observations."""

    def __init__(
        self, daily, quotes, out, max_trials=36, origins=None, horizon=HORIZON
    ):
        self.origins = origins or ORIGINS
        self.horizon = horizon
        self.cutoff = max(
            pd.Timestamp(o) + pd.Timedelta(days=horizon) for o in self.origins
        )
        self.daily = daily.loc[: self.cutoff].copy()
        self.quotes = quotes[
            (quotes.quote_date <= self.cutoff) & (quotes.dep_date <= self.cutoff)
        ].copy()
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.max_trials = max_trials
        self.trials = {}
        self.predictions = {}
        self.frozen = None
        self.plans = []
        self.current_cache = {}
        self.used = 0

    def event(self, tool, **data):
        with (self.out / "audit.jsonl").open("a") as f:
            f.write(
                json.dumps({"tool": tool, **data}, allow_nan=False, default=str) + "\n"
            )

    def mutable(self):
        if self.frozen is not None:
            raise ValueError("Choices frozen; no more exploration")

    def plan(self, text):
        self.mutable()
        if not text.strip() or len(text) > 4000:
            raise ValueError("Plan must be 1–4000 characters")
        self.plans.append(text)
        self.event("record_plan", text=text)
        return {"saved": True, "trials_remaining": self.max_trials - self.used}

    def inspect(self, component):
        if component not in COMPONENTS:
            raise ValueError("Unknown component")
        # Inspection is restricted to the FIRST training cutoff, not validation or final observations.
        origin = pd.Timestamp(self.origins[0])
        frame = self.daily.loc[:origin]
        if component in TARGETS:
            y = frame[component]
            result = {
                "component": component,
                "through": str(origin.date()),
                "n": len(y),
                "missing": int(y.isna().sum()),
                "mean": float(y.mean()),
                "std": float(y.std()),
                "min": float(y.min()),
                "max": float(y.max()),
                "recent_28_mean": float(y.iloc[-28:].mean()),
                "weekday_means": y.groupby(y.index.dayofweek).mean().to_dict(),
                "autocorrelation": {
                    str(k): float(y.autocorr(k)) if y.nunique() > 1 else None
                    for k in [1, 7, 28]
                },
            }
        else:
            q = self.quotes[
                (self.quotes.quote_date <= origin) & (self.quotes.dep_date <= origin)
            ]
            result = {
                "component": component,
                "through": str(origin.date()),
                "mature_rows": len(q),
                "candidates": CURVES[component],
            }
        self.event("inspect_data", component=component)
        return result

    def split(self, origin):
        o = pd.Timestamp(origin)
        dates = pd.date_range(o + pd.Timedelta(days=1), periods=self.horizon)
        train = self.daily.loc[:o]
        actual = self.daily.reindex(dates)
        if len(train) < 180 or actual.isna().any().any():
            raise ValueError("Incomplete development coverage")
        q = self.quotes
        train_q = q[(q.quote_date <= o) & (q.dep_date <= o)]
        hold = q[
            (q.quote_date > o) & (q.quote_date <= dates[-1]) & (q.dep_date <= dates[-1])
        ]
        return train, actual, train_q, hold

    def score_predictions(self, component, predictions):
        folds = []
        for origin, pred in zip(self.origins, predictions):
            actual = self.split(origin)[1][component]
            folds.append({"origin": origin, **metrics(actual, pred)})
        n = sum(f["n"] for f in folds)
        return {
            "score": float(np.sqrt(sum(f["rmse"] ** 2 * f["n"] for f in folds) / n)),
            "folds": folds,
        }

    def trial(self, component, config, rationale):
        self.mutable()
        if not self.plans:
            raise ValueError("Record an experiment plan first")
        if component not in COMPONENTS:
            raise ValueError("Unknown component")
        recipe = Recipe.model_validate(config)
        if component in CURVES:
            if recipe.family != "curve" or recipe.curve_name not in CURVES[component]:
                raise ValueError("Unsupported curve")
        elif recipe.family == "curve":
            raise ValueError("Curve recipe for daily target")
        if not rationale.strip() or len(rationale) > 2000:
            raise ValueError("Provide a short rationale")
        key = sha256(
            json.dumps([component, recipe.model_dump()], sort_keys=True).encode()
        ).hexdigest()[:16]
        if key in self.trials:
            return self.trials[key]
        if self.used >= self.max_trials:
            raise ValueError("Trial budget exhausted; select existing trials")
        self.used += 1
        started = time.monotonic()
        record = {
            "id": key,
            "component": component,
            "recipe": recipe.model_dump(),
            "rationale": rationale,
            "kind": "model",
        }
        self.event("trial_started", **record)
        try:
            predictions = []
            folds = []
            for origin in self.origins:
                train, actual, q, hold = self.split(origin)
                if component in CURVES:
                    c = curve_candidate(q, component, recipe.curve_name, fit_curves(q))
                    folds.append({"origin": origin, **curve_score(hold, component, c)})
                else:
                    if recipe.family == "current":
                        if origin not in self.current_cache:
                            self.current_cache[origin] = constrain(
                                baseline(train, actual.index)
                            )
                        pred = self.current_cache[origin][component].to_numpy()
                    else:
                        pred = predict_recipe(train, actual.index, component, recipe)
                    predictions.append(pred)
            if component in TARGETS:
                record.update(self.score_predictions(component, predictions))
                self.predictions[key] = predictions
            else:
                record.update(
                    score=sum(f["loss"] * f["n"] for f in folds)
                    / sum(f["n"] for f in folds),
                    folds=folds,
                )
            record["status"] = "ok"
        except Exception as e:
            record.update(status="failed", error=type(e).__name__, score=None)
        if key in self.predictions:
            pd.DataFrame(
                [
                    {"origin": o, "step": i + 1, "prediction": float(v)}
                    for o, values in zip(self.origins, self.predictions[key])
                    for i, v in enumerate(values)
                ]
            ).to_csv(self.out / f"validation_{key}.csv", index=False)
        record["seconds"] = time.monotonic() - started
        self.trials[key] = record
        self.save()
        self.event("trial_completed", **record)
        return record

    def ensemble(self, trial_ids, weights, rationale):
        self.mutable()
        if (
            len(trial_ids) < 2
            or len(trial_ids) > 3
            or len(set(trial_ids)) != len(trial_ids)
        ):
            raise ValueError("Choose 2–3 distinct trials")
        rows = [self.trials[t] for t in trial_ids]
        component = rows[0]["component"]
        if component not in TARGETS or any(
            r["component"] != component or r["status"] != "ok" or r["kind"] != "model"
            for r in rows
        ):
            raise ValueError("Use successful daily-model trials from one component")
        w = np.asarray(weights, float)
        if (
            len(w) != len(rows)
            or not np.isfinite(w).all()
            or (w <= 0).any()
            or not np.isclose(w.sum(), 1)
        ):
            raise ValueError("Positive weights must sum to one")
        if not rationale.strip() or len(rationale) > 2000:
            raise ValueError("Provide rationale")
        key = sha256(json.dumps([trial_ids, weights]).encode()).hexdigest()[:16]
        if key in self.trials:
            return self.trials[key]
        if self.used >= self.max_trials:
            raise ValueError("Trial budget exhausted")
        self.used += 1
        pred = [
            sum(weight * self.predictions[t][i] for t, weight in zip(trial_ids, w))
            for i in range(len(self.origins))
        ]
        record = {
            "id": key,
            "component": component,
            "kind": "ensemble",
            "members": trial_ids,
            "weights": weights,
            "rationale": rationale,
            "status": "ok",
            **self.score_predictions(component, pred),
        }
        self.trials[key] = record
        self.predictions[key] = pred
        pd.DataFrame(
            [
                {"origin": o, "step": i + 1, "prediction": float(v)}
                for o, values in zip(self.origins, pred)
                for i, v in enumerate(values)
            ]
        ).to_csv(self.out / f"validation_{key}.csv", index=False)
        self.save()
        self.event("ensemble", **record)
        return record

    def review(self, trial_id):
        row = self.trials[trial_id]
        result = dict(row)
        if trial_id in self.predictions:
            residuals = []
            for origin, pred in zip(self.origins, self.predictions[trial_id]):
                actual = self.split(origin)[1][row["component"]]
                residuals.extend(
                    {"weekday": d.dayofweek, "error": float(p - a), "horizon": i + 1}
                    for i, (d, p, a) in enumerate(zip(actual.index, pred, actual))
                )
            frame = pd.DataFrame(residuals)
            result["weekday_bias"] = frame.groupby("weekday").error.mean().to_dict()
            result["horizon_mae"] = (
                frame.assign(abs_error=frame.error.abs())
                .groupby("horizon")
                .abs_error.mean()
                .to_dict()
            )
        self.event("review_errors", trial_id=trial_id)
        return result

    def freeze(self, choices):
        self.mutable()
        if set(choices) != set(COMPONENTS):
            raise ValueError("Choose all seven forecasts and two curves")
        for component, choice in choices.items():
            row = self.trials.get(choice["trial_id"])
            if not row or row["status"] != "ok" or row["component"] != component:
                raise ValueError("Invalid selected trial")
            if not choice["reason"].strip() or len(choice["reason"]) > 2000:
                raise ValueError("Explain each selection")
            current = "current" if component in TARGETS else CURVES[component][0]
            if not any(
                r["status"] == "ok"
                and r["component"] == component
                and r["kind"] == "model"
                and (
                    r["recipe"]["family"] == current
                    or r["recipe"]["curve_name"] == current
                )
                for r in self.trials.values()
            ):
                raise ValueError("Evaluate current baseline for every component first")
        self.frozen = json.loads(json.dumps(choices))
        write_json(self.out / "frozen_choices.json", self.frozen)
        self.event("freeze_choices", choices=self.frozen)
        return {"frozen": True, "choices": self.frozen}

    def save(self):
        write_json(self.out / "trials.json", self.trials)
