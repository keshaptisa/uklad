"""Проверки ICVI на графах с известным ответом: направление «лучше/хуже» и совпадение с networkx."""
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad.quality import feature_icvi, graph_icvi, icvi_z  # noqa: E402


def cliques(K=3, n=10):
    A = np.zeros((K * n, K * n))
    for k in range(K):
        A[k * n:(k + 1) * n, k * n:(k + 1) * n] = 1
    np.fill_diagonal(A, 0)
    return A, np.repeat(np.arange(K), n)


def test_isolated_cliques_are_perfect():
    A, y = cliques(K=4)
    g = graph_icvi(A, y)
    assert g["AVI"] == pytest.approx(1.0)
    assert g["AVU"] == pytest.approx(0.0)
    assert g["MQ"] == pytest.approx(1 - 1 / 4)
    assert g["MQ_Mancoridis"] == pytest.approx(4.0)


def test_modularity_matches_networkx():
    rng = np.random.default_rng(1)
    G = nx.gnp_random_graph(60, 0.15, seed=1)
    for u, v in G.edges:
        G[u][v]["weight"] = rng.uniform(0.1, 2)
    A = nx.to_numpy_array(G, weight="weight")
    y = rng.integers(0, 4, 60)
    comms = [set(np.where(y == k)[0]) for k in range(4)]
    assert graph_icvi(A, y)["MQ"] == pytest.approx(nx.community.modularity(G, comms, weight="weight"), abs=1e-12)


def test_random_partition_avi_near_one_over_k():
    G = nx.gnp_random_graph(400, 0.05, seed=2)
    A = nx.to_numpy_array(G)
    y = np.random.default_rng(3).integers(0, 5, 400)
    assert graph_icvi(A, y)["AVI"] == pytest.approx(0.2, abs=0.03)


def test_true_partition_beats_random_on_all_indices():
    rng = np.random.default_rng(4)
    K, n = 4, 40
    y = np.repeat(np.arange(K), n)
    X = rng.normal(size=(K * n, 3)) + 4 * np.eye(K, 3)[y % 3] * (y[:, None] < 3)
    X[y == 3] += np.array([-4, -4, 0])
    P = np.where(y[:, None] == y[None, :], 0.3, 0.02)
    A = (rng.uniform(size=P.shape) < P).astype(float)
    A = np.triu(A, 1); A = A + A.T
    z = icvi_z(X, A, y, n_perm=30)
    assert all(v > 2 for v in z.values()), z


def test_feature_icvi_direction():
    rng = np.random.default_rng(5)
    y = np.repeat([0, 1], 50)
    X = rng.normal(size=(100, 2)) + 6 * y[:, None]
    good, bad = feature_icvi(X, y), feature_icvi(X, rng.permutation(y))
    assert good["SW"] > bad["SW"] and good["CH"] > bad["CH"] and good["S_Dbw"] < bad["S_Dbw"]


def test_dtw_matches_naive():
    from uklad.network import dtw_dist
    rng = np.random.default_rng(6)
    T = rng.normal(size=(7, 10, 2))

    def naive(a, b, w):
        L = len(a); acc = np.full((L + 1, L + 1), np.inf); acc[0, 0] = 0
        for t in range(1, L + 1):
            for u in range(max(1, t - w), min(L, t + w) + 1):
                acc[t, u] = np.linalg.norm(a[t - 1] - b[u - 1]) + min(acc[t - 1, u], acc[t, u - 1], acc[t - 1, u - 1])
        return acc[L, L]

    D = dtw_dist(T, window=2, chunk=3)
    for i in range(7):
        for j in range(7):
            assert D[i, j] == pytest.approx(naive(T[i], T[j], 2), rel=1e-5)


def test_lagcorr_finds_shift():
    from uklad.network import lagcorr_sim
    rng = np.random.default_rng(7)
    base = rng.normal(size=30)
    T = np.stack([base[2:26], base[1:25], base[0:24], rng.normal(size=24)])  # ряд 0 опережает ряд 2 на 2 мес.
    S, lag = lagcorr_sim(T, max_lag=2)
    assert S[0, 2] == pytest.approx(1.0, abs=1e-9) and abs(lag[0, 2]) == 2


def test_basic_mq_penalizes_inter_cluster_edges():
    # BasicMQ, в отличие от TurboMQ (= K·AVI), штрафует связи между типами: изолированные клики лучше, чем те же клики
    # с добавленными межкластерными рёбрами, а случайная разметка — хуже истинной
    A, y = cliques(K=3)
    iso = graph_icvi(A, y, basic=True)["MQ_basic"]
    B = A.copy()
    B[0, 10] = B[10, 0] = B[0, 20] = B[20, 0] = 1
    assert graph_icvi(B, y, basic=True)["MQ_basic"] < iso
    rnd = np.random.default_rng(0).permutation(y)
    assert graph_icvi(A, rnd, basic=True)["MQ_basic"] < iso
    assert graph_icvi(A, y)["MQ_Mancoridis"] == pytest.approx(3 * graph_icvi(A, y)["AVI"])
