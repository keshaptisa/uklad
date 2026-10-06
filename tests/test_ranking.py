"""Рейтинг методов: пороговое агрегирование Алескерова и правило Борда на игрушечных данных с известным ответом."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad.aggregate import three_grades, threshold_aggregation  # noqa: E402


def test_three_grades_thirds():
    g = three_grades(pd.Series([6, 5, 4, 3, 2, 1], index=list("abcdef")))
    assert g.tolist() == [1, 1, 2, 2, 3, 3]


def test_threshold_no_compensation():
    # «a» блестящ по двум критериям и провален по третьему; «b» везде средне-хорош.
    # Борда (сумма мест) ставит «a» не ниже «b», пороговое агрегирование — «b» выше: провал не компенсируется.
    Z = pd.DataFrame({"k1": [10, 8, 1], "k2": [10, 8, 2], "k3": [0, 8, 9]}, index=["a", "b", "c"])
    r = threshold_aggregation(Z)
    assert r.loc["b", "rank_threshold"] < r.loc["a", "rank_threshold"]
    assert r.loc["a", "rank_borda"] <= r.loc["b", "rank_borda"]


def test_dominating_method_first_everywhere():
    Z = pd.DataFrame({"k1": [3, 2, 1], "k2": [3, 1, 2], "k3": [3, 2, 1]}, index=["best", "x", "y"])
    r = threshold_aggregation(Z)
    assert r.index[0] == "best" and r.loc["best", "rank_threshold"] == 1 and r.loc["best", "rank_borda"] == 1
