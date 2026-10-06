"""Методы кластеризации и динамики на синтетике с известным ответом: planted partition граф с атрибутами."""
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp
from sklearn.metrics import adjusted_rand_score as ARI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import partition as C  # noqa: E402
from uklad import network as G  # noqa: E402
from uklad import tracking as TM  # noqa: E402


def planted(K=3, n=40, p_in=0.3, p_out=0.01, sep=3.0, seed=0):
    """K групп по n узлов: плотные внутри, редкие между; признаки — гауссовы облака с центрами на расстоянии sep."""
    rng = np.random.default_rng(seed)
    y = np.repeat(np.arange(K), n)
    P = np.where(y[:, None] == y[None, :], p_in, p_out)
    A = np.triu(rng.random(P.shape) < P, 1).astype(float)
    A = A + A.T
    X = rng.normal(size=(K * n, 4)) + sep * np.eye(K, 4)[y]
    return X, sp.csr_matrix(A), y


def test_kefrin_recovers_planted():
    X, A, y = planted()
    assert ARI(y, C.kefrin(X, C.modularity_rows(A), 3, seed=0)) > 0.95


def test_network_methods_recover_planted():
    X, A, y = planted()
    assert ARI(y, C.leiden_k(A, 3)) > 0.9
    assert ARI(y, C.louvain_k(A, 3)) > 0.9


def test_ward_connectivity_uses_graph():
    # признаки различают группы слабо, сеть — хорошо: ограничение связности должно помочь обычному Ward
    X, A, y = planted(sep=1.0, p_out=0.002)
    assert ARI(y, C.ward_net(X, A, 3)) > ARI(y, C.ward(X, 3)) + 0.2


def test_snf_keeps_shared_structure():
    # два взгляда видят одну и ту же группировку, третий — шум; слияние сохраняет группы
    X, A, y = planted(sep=4.0)
    rng = np.random.default_rng(1)
    D1 = np.linalg.norm(X[:, None] - X[None], axis=2)
    D2 = np.linalg.norm((X + rng.normal(scale=0.5, size=X.shape))[:, None] - X[None], axis=2)
    N = rng.random(D1.shape)
    W = G.snf([D1, D2, (N + N.T) / 2], K=10)
    nn = np.argsort(-W, 1)[:, 1:11]
    assert (y[nn] == y[:, None]).mean() > 0.9


def test_affect_alpha_direction():
    rng = np.random.default_rng(0)
    y = np.repeat([0, 1], 50)
    centers = np.array([[0.0, 0], [5, 5]])[y]
    noisy = centers + rng.normal(scale=2.0, size=centers.shape)
    calm = centers + rng.normal(scale=0.1, size=centers.shape)
    # история слегка смещена: при шумном срезе память ценнее (α велико), при спокойном — сдвиг важнее шума (α мало)
    hist = centers + 1.0
    assert TM.affect_alpha(hist, noisy, y) > 0.6
    assert TM.affect_alpha(hist, calm, y) < 0.1
    # история далеко от нынешних средних: памяти почти нет
    assert TM.affect_alpha(centers + 20, noisy, y) < 0.1


def test_deep_methods_run_and_find_structure():
    pytest.importorskip("torch")
    from uklad import gnn
    X, A, y = planted()
    for f in (gnn.gae_kmeans, gnn.dmon):
        lab = f(X, A, 3, seed=0)
        assert len(np.unique(lab)) == 3
        assert ARI(y, lab) > 0.8
