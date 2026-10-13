from datetime import date
from pathlib import Path

import polars as pl


PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def get_recommendation(departure_date: str) -> dict:
    """Read one saved recommendation for the current single-fleet dataset."""

    parsed_date = date.fromisoformat(departure_date)
    if parsed_date.isoformat() != departure_date:
        raise ValueError("Use a departure date in YYYY-MM-DD format.")

    path = PROCESSED_DIR / "optimal_yield_per_date.parquet"

    if not path.is_file():
        raise FileNotFoundError(f"Recommendation file not found: {path}")

    df = pl.read_parquet(path)

    required = {
        "date",
        "od_supply",
        "forecasted_quotes",
        "optimal_yield",
        "d_at_yield",
        "solver_status",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.with_columns(pl.col("date").cast(pl.Date))
    matches = df.filter(pl.col("date") == parsed_date)

    if matches.height == 0:
        return {
            "status": "not_found",
            "departure_date": departure_date,
            "message": "No saved recommendation exists for this date.",
        }

    if matches.height != 1:
        raise ValueError(
            f"Expected one recommendation for {departure_date}; "
            f"found {matches.height}."
        )

    row = matches.row(0, named=True)
    row["date"] = row["date"].isoformat()

    notes = [
        "Fleet scope comes from the dataset; this file has no fleet identifier.",
        "This file has no engine run identifier.",
    ]

    if row["solver_status"] == "DNQ_zero_supply":
        notes.append(
            "optimal_yield is a DNQ marker, not an actionable selling price. "
            "d_at_yield is set to zero by the DNQ branch."
        )
    elif row["solver_status"].startswith("error:"):
        notes.append(
            "The saved yield is a solver fallback, not a successful solution."
        )

    return {
        "status": "ok",
        "source_file": path.name,
        "evidence_type": "saved_engine_output",
        "yield_unit": "USD per estimated flight-time hour",
        "recommendation": row,
        "notes": notes,
    }

def get_supply_breakdown(departure_date: str) -> dict:
    """Explain saved supply using its recorded capacity and deductions."""
    import math

    parsed_date = date.fromisoformat(departure_date)
    if parsed_date.isoformat() != departure_date:
        raise ValueError("Use a departure date in YYYY-MM-DD format.")

    path = PROCESSED_DIR / "jan2026_od_supply.parquet"

    if not path.is_file():
        raise FileNotFoundError(f"Supply file not found: {path}")

    df = pl.read_parquet(path)

    numeric_columns = [
        "num_tails",
        "delivered_tails_fc",
        "raw_leg_supply_fc",
        "program_live_legs_fc",
        "non_program_live_legs_fc",
        "current_od_adjusted",
        "od_supply",
    ]
    missing = {"date", *numeric_columns} - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.with_columns(pl.col("date").cast(pl.Date))
    matches = df.filter(pl.col("date") == parsed_date)

    if matches.height == 0:
        return {
            "status": "not_found",
            "departure_date": departure_date,
            "message": "No saved supply record exists for this date.",
        }

    if matches.height != 1:
        raise ValueError(
            f"Expected one supply record for {departure_date}; "
            f"found {matches.height}."
        )

    row = matches.row(0, named=True)

    for column in numeric_columns:
        value = row[column]
        if value is None or not math.isfinite(float(value)):
            raise ValueError(f"Missing or non-finite value in {column}.")

    total_deductions = (
        row["program_live_legs_fc"]
        + row["non_program_live_legs_fc"]
        + row["current_od_adjusted"]
    )
    balance_before_clipping = row["raw_leg_supply_fc"] - total_deductions
    reconstructed_supply = max(0.0, balance_before_clipping)

    arithmetic_matches = math.isclose(
        reconstructed_supply,
        row["od_supply"],
        rel_tol=1e-9,
        abs_tol=1e-6,
    )

    recommendation = get_recommendation(departure_date)
    recommendation_matches = None

    if recommendation["status"] == "ok":
        recommendation_matches = math.isclose(
            row["od_supply"],
            recommendation["recommendation"]["od_supply"],
            rel_tol=1e-9,
            abs_tol=1e-6,
        )

    notes = [
        "The pre-clipping balance is reconstructed from saved components.",
        "Non-program consumption currently includes OD activity.",
        "A zero existing-OD adjustment does not prove no OD bookings existed.",
        "Matching values do not establish that files share an engine run.",
    ]

    if not arithmetic_matches:
        notes.append("Reconstructed supply differs from saved supply.")

    if recommendation_matches is False:
        notes.append("Supply differs from the recommendation file.")

    if recommendation_matches is None:
        notes.append("No recommendation was available for comparison.")

    consistent = arithmetic_matches and recommendation_matches is True

    return {
        "status": "ok" if consistent else "needs_review",
        "departure_date": departure_date,
        "source_file": path.name,
        "evidence_type": "saved_components_with_reconstructed_arithmetic",
        "aircraft": {
            "fleet_size": row["num_tails"],
            "forecast_delivered": row["delivered_tails_fc"],
        },
        "supply_legs": {
            "raw_capacity": row["raw_leg_supply_fc"],
            "program_deduction": row["program_live_legs_fc"],
            "non_program_deduction": row["non_program_live_legs_fc"],
            "existing_od_adjusted_deduction": row["current_od_adjusted"],
            "total_deductions": total_deductions,
            "balance_before_clipping": balance_before_clipping,
            "clipped_to_zero": balance_before_clipping < 0,
            "reconstructed_remaining": reconstructed_supply,
            "saved_remaining": row["od_supply"],
        },
        "checks": {
            "arithmetic_matches_saved_supply": arithmetic_matches,
            "supply_matches_recommendation": recommendation_matches,
        },
        "notes": notes,
    }