import pandas as pd
import pytest
from src.synthetic_robustness import ORIGINS, PATHS, summarize
from src.model_benchmark import TARGETS


def test_windows_cover_stress_and_do_not_overlap():
    windows = [
        set(pd.date_range(pd.Timestamp(o) + pd.Timedelta(days=1), periods=90))
        for o in ORIGINS
    ]
    assert len(windows) == 12
    assert len(set.union(*windows)) == 1080
    for year in (2033, 2034, 2035):
        assert pd.Timestamp(f"{year}-06-01") in set.union(*windows)
        assert pd.Timestamp(f"{year}-07-15") in set.union(*windows)
    assert len(PATHS) == 5


def test_summary_uses_same_price_dates_and_pooled_rmse():
    records, prices = [], []
    for name in ("current", "frozen_agent"):
        for origin, error in [("2032-12-31", 3), ("2033-03-31", 4)]:
            records.append(
                {
                    "path": "test",
                    "horizon": 14,
                    "candidate": name,
                    "forecast_errors": {
                        c: {"n": 1, "rmse": error, "mae": error}
                        for c in TARGETS + ["remaining_supply_proxy"]
                    },
                }
            )
            prices.append(
                {
                    "path": "test",
                    "horizon": 14,
                    "origin": origin,
                    "date": origin,
                    "candidate": name,
                    "yield": None if name == "frozen_agent" and error == 4 else 8000,
                    "reference_yield": 7000,
                    "status": "solved",
                    "reference_status": "solved",
                }
            )
    result = summarize(records, pd.DataFrame(prices))
    assert len(result) == 2
    for r in result:
        assert r["common_price_n"] == 1
        assert r["common_price_mae"] == 1000
        assert r["forecast_errors"]["remaining_supply_proxy"]["rmse"] == pytest.approx(
            (12.5) ** 0.5
        )
