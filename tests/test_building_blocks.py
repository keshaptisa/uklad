"""Строительные блоки конвейера на маленьких примерах с известным ответом: графы, признаки, отслеживание, интерпретация."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import attributes as F  # noqa: E402
from uklad import network as G  # noqa: E402
from uklad import tracking as TM  # noqa: E402
from uklad.aggregate import copeland, threshold_aggregation  # noqa: E402
from uklad.explain import eta_squared  # noqa: E402


# ---------- графы ----------
def test_knn_graph_is_symmetric_without_loops_and_has_min_degree_k():
    rng = np.random.default_rng(0)
    S = G.cosine_sim(rng.normal(size=(50, 4)))
    A = G.knn_graph(S, 5)
    assert (abs(A - A.T)).sum() == pytest.approx(0)
    assert A.diagonal().sum() == 0
    assert (np.asarray((A > 0).sum(1)).ravel() >= 5).all()


def test_road_distance_and_similarity():
    conn = pd.DataFrame({"territory_id_x": [1, 2], "territory_id_y": [2, 3], "distance": [100.0, 50.0],
                         "type": ["highway", "railway"]})
    D = G.road_distance(np.array([1, 2, 3]), conn, "highway")
    assert D[0, 1] == D[1, 0] == 100 and np.isinf(D[1, 2]) and D[0, 0] == 0
    assert G.road_sim(np.array([0.0, 200.0]), 200.0) == pytest.approx([1.0, np.exp(-1)])


def test_edge_jaccard_bounds():
    A = sp.csr_matrix(np.array([[0, 1, 1], [1, 0, 0], [1, 0, 0]], float))
    B = sp.csr_matrix(np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], float))
    assert G.edge_jaccard(A, A) == pytest.approx(1.0)
    assert 0 < G.edge_jaccard(A, B) < 1


# ---------- признаки ----------
def test_clr_rows_sum_to_zero_and_shares_to_one():
    w = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 2.0], "c": [6.0, 6.0]})
    s = w.div(w.sum(1), axis=0)
    assert np.allclose(s.sum(1), 1)
    assert np.allclose(F.clr(s).sum(1), 0)


def test_standardize_zero_mean_unit_sd_and_clip():
    X = pd.DataFrame({"x": np.r_[np.zeros(99), 1000.0]})
    Z = F.standardize(X, clip=4.0)
    assert Z["x"].abs().max() <= 4.0 + 1e-9


# ---------- отслеживание ----------
def test_persistent_switches_ignores_short_runs():
    L = np.array([[0] * 4 + [1] * 2 + [0] * 4 + [2] * 5]).T     # 15 месяцев, один МО
    ps = TM.persistent_switches(L, min_run=3)
    assert list(zip(ps["from"], ps["to"])) == [(0, 2)]          # «качели» 0→1→0 длиной 2 — не переход


def test_transition_matrix_is_row_stochastic():
    L = np.array([[0, 0, 1], [0, 1, 1]])                         # 2 месяца × 3 МО: из типа 0 один остался, один ушёл
    M = TM.transition_matrix(L, 2)
    assert np.allclose(M.sum(1), 1)
    assert M[0, 1] == pytest.approx(0.5) and M[1, 1] == pytest.approx(1.0)


def test_monic_survival_with_overlap():
    L0 = np.array([0] * 10 + [1] * 10)
    L1 = np.array([0] * 10 + [1] * 5 + [2] * 5)
    ev = TM.monic_events(L0, L1).set_index("from")
    assert ev.loc[0, "event"] == "выживание" and ev.loc[0, "overlap"] == pytest.approx(1.0)
    assert ev.loc[1, "overlap"] == pytest.approx(0.5)            # половина типа 1 ушла в новый тип


# ---------- рейтинг и интерпретация ----------
def test_copeland_condorcet_winner_first():
    Z = pd.DataFrame({"c1": [3, 2, 1], "c2": [3, 1, 2], "c3": [1, 3, 2]}, index=list("abc"))
    r = copeland(Z)
    assert r.index[0] == "a" and r.loc["a", "rank_copeland"] == 1


def test_threshold_and_copeland_agree_on_dominant_method():
    Z = pd.DataFrame({"c1": [5, 1, 2, 3], "c2": [5, 2, 1, 3], "c3": [5, 3, 2, 1]}, index=list("abcd"))
    assert threshold_aggregation(Z).index[0] == copeland(Z).index[0] == "a"


def test_eta_squared_extremes():
    y = np.repeat([0, 1], 50)
    assert eta_squared(pd.Series(y * 10.0), y) == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    assert eta_squared(pd.Series(rng.normal(size=100)), rng.permutation(y)) < 0.1
