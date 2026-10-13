"""Read-only reconstruction of a saved DPE run; never fits models or reprices."""
from __future__ import annotations

import ast
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "recommendation": "data/processed/optimal_yield_per_date.parquet",
    "supply": "data/processed/jan2026_od_supply.parquet",
    "quotes": "data/processed/jan2026_may2026_quotes_forecast.parquet",
    "parameters": "data/processed/elasticity_params.json",
    "solver": "notebooks/09_solver.ipynb",
}
CAVEATS = [
    "This is a reconstruction from current saved files, not an original execution trace. File hashes identify this evidence snapshot, not a historical run.",
    "The dataset has one fleet scope but no row-level fleet or engine run identifier.",
    "Non-program consumption currently includes OD activity. A zero existing-OD adjustment does not prove there were no bookings.",
    "Quote forecasts use enquiry dates; supply uses departure dates. The current engine joins the same calendar date.",
    "Conversion is observational, uses mixed quoted/realised yields, and excludes many bookings with missing yield. It is not a causal price effect.",
    "Expected fractional bookings are forecasts, not a sell-out guarantee or proof of profit optimality.",
]


def finite(value, label):
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label}: expected a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label}: expected a finite number")
    return number


def same(a, b, tolerance=1e-6):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=tolerance)


class EvidenceStore:
    """Load a fixed in-memory snapshot once for each explanation request."""

    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.blobs = {key: (self.root / path).read_bytes() for key, path in FILES.items()}
        self.sources = {
            key: {"path": FILES[key], "sha256": sha256(data).hexdigest()}
            for key, data in self.blobs.items()
        }
        self.snapshot_id = sha256(json.dumps(self.sources, sort_keys=True).encode()).hexdigest()
        self.tables = {
            key: pl.read_parquet(BytesIO(self.blobs[key]))
            for key in ("recommendation", "supply", "quotes")
        }
        self.params = json.loads(self.blobs["parameters"])
        # Read literal constants only. Never execute notebook cells.
        constants = {}
        for cell in json.loads(self.blobs["solver"])["cells"]:
            if cell["cell_type"] != "code":
                continue
            for node in ast.parse("".join(cell["source"])).body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in {
                            "YIELD_FLOOR", "YIELD_CEILING", "Y_MEDIAN"
                        }:
                            constants[target.id] = finite(ast.literal_eval(node.value), target.id)
        self.floor = constants["YIELD_FLOOR"]
        self.ceiling = constants["YIELD_CEILING"]
        if not 0 < self.floor < self.ceiling:
            raise ValueError("Invalid solver bounds")
        curve = self.params["quote_count_elasticity"]
        conv = self.params["conversion_elasticity"]
        if curve["method"] != "lowess" or conv["method"] != "exponential":
            raise ValueError("Unsupported demand model: update the evidence adapter")
        if conv.get("b_unit") != "per_$k":
            raise ValueError("Conversion coefficient must be expressed per $1,000")
        self.x = np.array(curve["x"], dtype=float)
        self.y = np.array(curve["y_normalized"], dtype=float)
        if (self.x.ndim != 1 or self.y.ndim != 1 or len(self.x) < 2
            or len(self.x) != len(self.y) or not np.isfinite(self.x).all()
            or not np.isfinite(self.y).all() or not (np.diff(self.x) > 0).all()
            or (self.y < 0).any()):
            raise ValueError("Invalid LOWESS interpolation points")
        self.a = finite(conv["a"], "a")
        self.b = finite(conv["b"], "b")
        if self.a < 0 or self.b < 0:
            raise ValueError("Negative conversion parameters")

    def row(self, table, day, columns):
        df = self.tables[table]
        missing = {"date", *columns} - set(df.columns)
        if missing:
            raise ValueError(f"{table}: missing columns {sorted(missing)}")
        df = df.with_columns(pl.col("date").cast(pl.Date))
        rows = df.filter(pl.col("date") == day)
        if rows.height > 1:
            raise ValueError(f"{table}: duplicate records for {day}")
        if rows.height == 0:
            return None
        row = rows.row(0, named=True)
        return {key: finite(row[key], f"{table}.{key}") for key in columns} | {
            "date": day.isoformat(),
            **({"solver_status": row["solver_status"]} if table == "recommendation" else {}),
        }

    def demand(self, yield_value, quotes):
        multiplier = float(np.interp(yield_value, self.x, self.y))
        conversion = self.a * math.exp(-self.b * yield_value / 1000)
        if not 0 <= conversion <= 1:
            raise ValueError("Reconstructed conversion is outside [0, 1]")
        bookings = finite(quotes * multiplier * conversion, "expected_bookings")
        return {"yield": yield_value, "quote_multiplier": multiplier,
                "conversion_probability": conversion, "expected_bookings": bookings}

    def explain(self, departure_date):
        day = date.fromisoformat(departure_date)
        if day.isoformat() != departure_date:
            raise ValueError("Use YYYY-MM-DD")
        rec = self.row("recommendation", day, [
            "od_supply", "forecasted_quotes", "optimal_yield", "d_at_yield"
        ])
        base = {"departure_date": departure_date, "snapshot_id": self.snapshot_id,
                "sources": self.sources, "historical_run_id": None}
        if rec is None:
            return base | {"status": "not_found", "message": "No saved recommendation for this date."}
        if not isinstance(rec["solver_status"], str):
            raise ValueError("Invalid solver status")
        supply = self.row("supply", day, ["raw_leg_supply_fc", "program_live_legs_fc",
            "non_program_live_legs_fc", "current_od_adjusted", "od_supply"])
        quotes = self.row("quotes", day, ["forecasted_quotes", "yhat_lower", "yhat_upper"])
        if supply is None or quotes is None:
            return base | {"status": "needs_review", "recommendation": rec,
                          "message": "Recommendation exists but supply or quote evidence is missing."}
        if any(v < 0 for r in [rec, supply] for k, v in r.items()
               if k not in {"date", "solver_status"}):
            raise ValueError("Negative price, capacity, consumption, or forecast")
        if quotes["forecasted_quotes"] < 0:
            raise ValueError("Negative quote forecast")
        deductions = sum(supply[k] for k in ["program_live_legs_fc", "non_program_live_legs_fc", "current_od_adjusted"])
        raw_balance = supply["raw_leg_supply_fc"] - deductions
        supply.update(total_deductions=deductions, balance_before_clipping=raw_balance,
                      reconstructed_supply=max(0., raw_balance), clipped_to_zero=raw_balance < 0)
        points = {name: self.demand(y, quotes["forecasted_quotes"]) for name, y in
                  [("floor", self.floor), ("selected", rec["optimal_yield"]), ("ceiling", self.ceiling)]}
        capacity = rec["od_supply"]
        if capacity == 0:
            expected_status = "DNQ_zero_supply"
            reason = "Forecast deductions exhaust capacity; the engine clips remaining supply to zero and emits DNQ."
        elif points["floor"]["expected_bookings"] <= capacity:
            expected_status = "demand_below_floor"
            reason = "Expected bookings at the minimum yield do not exceed remaining capacity, so the engine selects the floor."
        elif points["ceiling"]["expected_bookings"] >= capacity:
            expected_status = "demand_above_ceiling"
            reason = "Expected bookings still meet or exceed capacity at the maximum yield, so the engine selects the ceiling."
        else:
            expected_status = "solved"
            reason = "Demand brackets remaining capacity between the bounds; the saved yield should lie near the crossing."
        # Allow the notebook's $1 root tolerance plus whole-dollar saved-yield rounding.
        neighbourhood = [self.demand(rec["optimal_yield"] + delta, quotes["forecasted_quotes"])["expected_bookings"]
                         for delta in [-1.5, 0, 1.5]]
        demand_tolerance = .0051 + max(abs(v - points["selected"]["expected_bookings"]) for v in neighbourhood)
        target = {"DNQ_zero_supply": self.ceiling, "demand_below_floor": self.floor,
                  "demand_above_ceiling": self.ceiling}.get(expected_status)
        selected_matches = (same(rec["optimal_yield"], target) if target is not None else
                            min(neighbourhood) - 1e-6 <= capacity <= max(neighbourhood) + 1e-6)
        checks = {
            "supply_arithmetic": same(supply["reconstructed_supply"], supply["od_supply"]),
            "recommendation_supply": same(capacity, supply["od_supply"]),
            "recommendation_quotes": same(rec["forecasted_quotes"], quotes["forecasted_quotes"]),
            "quote_interval_order": quotes["yhat_lower"] <= quotes["yhat_upper"],
            "solver_branch": rec["solver_status"] == expected_status,
            "yield_within_bounds": self.floor <= rec["optimal_yield"] <= self.ceiling,
            "selected_yield_matches_branch": selected_matches,
            "saved_demand": (same(rec["d_at_yield"], 0) if expected_status == "DNQ_zero_supply" else
                             same(rec["d_at_yield"], points["selected"]["expected_bookings"], demand_tolerance)),
        }
        notes = list(CAVEATS)
        if self.params.get("yield_floor") != self.floor:
            notes.append(f"Parameter file floor is {self.params.get('yield_floor')}; solver notebook floor is {self.floor}. Checks use the notebook floor.")
        if expected_status == "DNQ_zero_supply":
            notes.append("DNQ yield and saved zero demand are markers. Reconstructed demand at the ceiling is diagnostic, not an offer to sell.")
        facts = {}
        for section, values in [("recommendation", rec), ("supply", supply), ("quotes", quotes)]:
            for key, value in values.items():
                facts[f"{section}.{key}"] = value
        for name, point in points.items():
            for key, value in point.items():
                facts[f"demand.{name}.{key}"] = value
        facts.update({"solver.expected_status": expected_status, "solver.reason": reason})
        return base | {"status": "ok" if all(checks.values()) else "needs_review",
            "recommendation": rec, "supply": supply, "quotes": quotes,
            "demand": {"formula": "quotes * interpolated_multiplier * a * exp(-b * yield / 1000)",
                       "a": self.a, "b_per_1000": self.b, "points": points},
            "solver": {"expected_status": expected_status, "reason": reason,
                       "configuration_source": FILES["solver"], "floor": self.floor, "ceiling": self.ceiling},
            "checks": checks, "notes": notes, "facts": facts}


def render_report(report):
    lines = [f"DPE explanation — {report['departure_date']}", f"Evidence status: {report['status']}"]
    if "solver" not in report:
        return "\n".join(lines + [report["message"]])
    r, s = report["recommendation"], report["supply"]
    label = "DNQ marker" if r["solver_status"] == "DNQ_zero_supply" else "Saved yield"
    lines += [f"{label}: ${r['optimal_yield']:,.0f}/EFT hour | {r['solver_status']}",
        f"Supply: {s['raw_leg_supply_fc']:.4f} - {s['program_live_legs_fc']:.4f} - "
        f"{s['non_program_live_legs_fc']:.4f} - {s['current_od_adjusted']:.4f} = "
        f"{s['balance_before_clipping']:.4f}; after clipping: {s['reconstructed_supply']:.4f} legs.",
        f"Forecast enquiries: {report['quotes']['forecasted_quotes']:.2f}"]
    for name, p in report["demand"]["points"].items():
        lines.append(f"Demand at {name} (${p['yield']:,.0f}): {p['expected_bookings']:.4f} expected bookings; "
                     f"multiplier {p['quote_multiplier']:.4f}, conversion {p['conversion_probability']:.2%}.")
    lines += ["Reconstructed decision: " + report["solver"]["reason"],
              "Checks: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in report["checks"].items()),
              "Limitations:"] + ["- " + note for note in report["notes"]]
    return "\n".join(lines + ["Evidence snapshot: " + report["snapshot_id"]])
