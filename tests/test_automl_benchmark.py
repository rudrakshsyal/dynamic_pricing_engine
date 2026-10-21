import pytest
from src.automl_benchmark import choose, RECIPES, CURVES
from src.model_benchmark import TARGETS


def test_selection_uses_validation_and_ignores_failed_trials():
    rows = [
        {"id": "bad", "status": "failed", "score": None},
        {"id": "current", "status": "ok", "score": 2},
        {"id": "winner", "status": "ok", "score": 1},
    ]
    assert choose(rows)["id"] == "winner"


def test_exact_ties_keep_first_and_no_success_fails():
    rows = [
        {"id": "current", "status": "ok", "score": 1},
        {"id": "other", "status": "ok", "score": 1},
    ]
    assert choose(rows)["id"] == "current"
    with pytest.raises(ValueError):
        choose([{"status": "failed", "score": None}])
    assert len(TARGETS) * len(RECIPES) + sum(map(len, CURVES.values())) == 34
