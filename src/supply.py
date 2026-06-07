"""
supply.py
─────────
Computes daily OD Supply for a given forecast horizon.

Formula:
    OD_Supply(date) = raw_leg_supply(date)
                    - program_live_legs(date)
                    - non_program_live_legs(date)
                    - sum_over_callout_buckets[
                          currentOD_legs(bucket) × (1 - cancRate(bucket))
                      ]

Inputs (all pre-computed by upstream models):
    - jan2026_availability_forecast.parquet
    - jan2026_legs_forecast.parquet
    - cancellation_lookup.json

Author: Rudraksh Syal
"""

import polars as pl
import json
import numpy as np
from pathlib import Path
from typing import Optional


# ── constants ─────────────────────────────────────────────────────────────────
LIVE_LEGS_PER_TAIL = 1.06   # historical constant, NREG US fleet


def load_inputs(processed_dir: Path) -> tuple:
    """
    Load all pre-computed forecast artifacts from the processed data directory.

    Returns:
        df_avail      : daily availability forecast (delivered_tails, raw_leg_supply)
        df_legs       : daily leg count forecasts (program, non-program)
        cancel_lookup : dict mapping callout bucket → cancellation rate
    """
    df_avail = pl.read_parquet(processed_dir / "jan2026_availability_forecast.parquet")
    df_legs  = pl.read_parquet(processed_dir / "jan2026_legs_forecast.parquet")

    with open(processed_dir / "cancellation_lookup.json") as f:
        cancel_lookup = json.load(f)

    return df_avail, df_legs, cancel_lookup


def get_cancellation_rate(callout_days: int, cancel_lookup: dict) -> float:
    """
    Look up cancellation rate for a given callout in days.

    Bucket definitions (match EDA-derived lookup):
        0-7d   : last minute
        8-30d  : near term
        31-90d : medium advance
        91d+   : far out

    Args:
        callout_days  : days between solve date and departure date
        cancel_lookup : dict from cancellation_lookup.json

    Returns:
        cancellation rate as a float (e.g., 0.171 for 17.1%)
    """
    if callout_days <= 7:
        return cancel_lookup["0-7d"]
    elif callout_days <= 30:
        return cancel_lookup["8-30d"]
    elif callout_days <= 90:
        return cancel_lookup["31-90d"]
    else:
        return cancel_lookup["91d+"]


def compute_od_supply(
    processed_dir: Path,
    solve_date: Optional[str] = None,
    current_od_bookings: Optional[dict] = None,
) -> pl.DataFrame:
    """
    Compute OD Supply for each day in the forecast horizon (Jan 2026).

    Args:
        processed_dir       : path to data/processed/
        solve_date          : ISO date string of when optimizer runs (e.g. "2025-12-15")
                              Used to compute callout for existing OD bookings.
                              Defaults to "2025-12-31" (conservative: last day before Jan).
        current_od_bookings : dict of {date_str: confirmed_od_legs_count}
                              for departures already booked as of solve_date.
                              Defaults to {} (MVP: no confirmed bookings assumed).
                              Example: {"2026-01-05": 3, "2026-01-12": 5}

    Returns:
        Polars DataFrame with columns:
            date, num_tails, delivered_tails_fc, raw_leg_supply_fc,
            program_live_legs_fc, non_program_live_legs_fc,
            current_od_adjusted, od_supply
    """

    # ── defaults ─────────────────────────────────────────────────────────────
    if solve_date is None:
        solve_date = "2025-12-31"
    if current_od_bookings is None:
        current_od_bookings = {}

    # ── load ──────────────────────────────────────────────────────────────────
    df_avail, df_legs, cancel_lookup = load_inputs(processed_dir)

    # ── join availability + legs forecasts on date ────────────────────────────
    # normalise date column name: availability uses "date", legs uses "date"
    df = df_avail.join(df_legs, on="date", how="left")

    # ── compute current OD adjusted for cancellation ──────────────────────────
    # For each departure date, compute:
    #   callout = departure_date - solve_date
    #   cancel_rate = lookup(callout)
    #   current_od_adjusted = confirmed_od_legs × (1 - cancel_rate)

    dates = df["date"].to_list()
    current_od_adjusted = []

    for dep_date in dates:
        dep_str = str(dep_date)[:10]   # "2026-01-01"
        confirmed_legs = current_od_bookings.get(dep_str, 0)

        if confirmed_legs > 0:
            # compute callout in days
            from datetime import date
            solve_d  = date.fromisoformat(solve_date)
            dep_d    = date.fromisoformat(dep_str)
            callout  = (dep_d - solve_d).days
            crate    = get_cancellation_rate(callout, cancel_lookup)
            adjusted = confirmed_legs * (1 - crate)
        else:
            adjusted = 0.0

        current_od_adjusted.append(adjusted)

    # ── apply supply formula ──────────────────────────────────────────────────
    df = df.with_columns(
        pl.Series("current_od_adjusted", current_od_adjusted)
    ).with_columns(
        (
            pl.col("raw_leg_supply_fc")
            - pl.col("program_live_legs_fc")
            - pl.col("non_program_live_legs_fc")
            - pl.col("current_od_adjusted")
        ).alias("od_supply")
    )

    # ── clip supply to non-negative (supply can't be < 0) ─────────────────────
    # If all models overestimate consumption, floor at 0
    df = df.with_columns(
        pl.col("od_supply").clip(lower_bound=0).alias("od_supply")
    )

    return df.select([
        "date",
        "num_tails",
        "delivered_tails_fc",
        "raw_leg_supply_fc",
        "program_live_legs_fc",
        "non_program_live_legs_fc",
        "current_od_adjusted",
        "od_supply",
    ])