"""Методы кластеризации: по признакам, по сети и совместные (признаки + сеть).

- kmeans, ward, gmm — только признаки;
- spectral, leiden — только сеть;
- KEFRiN (Shalileh & Mirkin, Entropy 2022) — признаки и сеть вместе. Своя реализация по статье
  (код авторов без лицензии в репозиторий не включаем). Модель восстановления данных Миркина:
      y_iv = c_kv + f_iv,   p_ij = λ_kj + e_ij  для i ∈ S_k,
  критерий  F = ρ Σ_k Σ_{i∈S_k} d(y_i, c_k) + ξ Σ_k Σ_{i∈S_k} d(p_i, λ_k)  минимизируется чередованием:
  назначение в кластер с минимальной суммой расстояний → пересчёт центров. d — квадрат евклидова (KEFRiNe)
  или косинусное (KEFRiNc) расстояние. Строки сети p_i — модулярностная предобработка B = A − k kᵀ/2m
  (вычитаем ожидаемое число связей), так что «сетевой центр» λ_k показывает, с какими МО кластер связан сверх случайного.
  Веса: ρ = 1, ξ уравнивает суммарный разброс двух пространств (иначе одно из них доминирует).
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
from sklearn.mixture import GaussianMixture


# ---------- признаки ----------
def kmeans(X, K, seed=0, init="k-means++", n_init=20):
    if isinstance(init, np.ndarray):
        n_init = 1
    return KMeans(K, init=init, n_init=n_init, random_state=seed).fit_predict(X)


def ward(X, K, **_):
    return AgglomerativeClustering(K, linkage="ward").fit_predict(X)


def ward_net(X, A, K, **_):
    """Ward с ограничением связности (признаки + сеть): сливать можно только кластеры, соединённые ребром сети."""
    return AgglomerativeClustering(K, linkage="ward", connectivity=sp.csr_matrix(A)).fit_predict(X)


def gmm(X, K, seed=0, **_):
    return GaussianMixture(K, covariance_type="diag", n_init=5, random_state=seed).fit_predict(X)


# ---------- сеть ----------
def spectral(A, K, seed=0, **_):
    return SpectralClustering(K, affinity="precomputed", random_state=seed, assign_labels="cluster_qr").fit_predict(
        sp.csr_matrix(A))


def _igraph(A):
    import igraph as ig
    A = sp.triu(sp.csr_matrix(A), 1).tocoo()
    g = ig.Graph(n=A.shape[0], edges=list(zip(A.row.tolist(), A.col.tolist())), directed=False)
    g.es["weight"] = A.data.tolist()
    return g


def leiden(A, resolution=1.0, seed=0, **_):
    import leidenalg as la
    g = _igraph(A)
    p = la.find_partition(g, la.RBConfigurationVertexPartition, weights="weight",
                          resolution_parameter=resolution, seed=seed, n_iterations=-1)
    return np.array(p.membership)


def louvain(A, resolution=1.0, seed=0, **_):
    """Louvain (Blondel et al., 2008) — предшественник Leiden; igraph multilevel, ГСЧ igraph фиксируется seed."""
    import random

    import igraph as ig
    ig.set_random_number_generator(random.Random(seed))
    g = _igraph(A)
    return np.array(g.community_multilevel(weights="weight", resolution=resolution).membership)


def louvain_k(A, K, seed=0, **kw):
    return leiden_k(A, K, seed=seed, part=louvain, **kw)


def leiden_k(A, K, seed=0, lo=0.01, hi=3.0, tol=0, iters=30, part=None, **_):
    """Leiden с подбором разрешения так, чтобы число крупных сообществ (≥1% узлов) было K; мелкие — к ближайшему по связям."""
    n = A.shape[0]
    best = None
    for _ in range(iters):
        r = np.sqrt(lo * hi)
        y = (part or leiden)(A, r, seed)
        sizes = np.bincount(y)
        k_big = (sizes >= 0.01 * n).sum()
        if best is None or abs(k_big - K) < abs(best[0] - K):
            best = (k_big, y)
        if k_big == K:
            break
        if k_big < K:
            lo = r
        else:
            hi = r
    return merge_small(A, best[1], min_size=int(0.01 * n))


def merge_small(A, y, min_size):
    """Сообщества меньше min_size переносим к сообществу, с которым у узла больше всего связей."""
    A = sp.csr_matrix(A)
    y = y.copy()
    sizes = np.bincount(y)
    big = np.where(sizes >= min_size)[0]
    for i in np.where(~np.isin(y, big))[0]:
        row = A.getrow(i)
        w = np.zeros(y.max() + 1)
        np.add.at(w, y[row.indices], row.data)
        w[~np.isin(np.arange(len(w)), big)] = -1
        y[i] = big[np.argmax(w)] if w.max() > 0 else big[0]
    _, y = np.unique(y, return_inverse=True)
    return y


def temporal_leiden(As, omega=1.0, resolution=1.0, seed=0):
    """Многослойная модулярность (Mucha et al., Science 2010): слой — месяц, узел связан сам с собой в соседних месяцах весом ω.
    Возвращает метки T × N, согласованные во времени по построению."""
    import leidenalg as la
    graphs = []
    for A in As:
        g = _igraph(A)
        g.vs["id"] = list(range(A.shape[0]))
        graphs.append(g)
    membership, _ = la.find_partition_temporal(graphs, la.RBConfigurationVertexPartition, interslice_weight=omega,
                                               vertex_id_attr="id", weights="weight",
                                               resolution_parameter=resolution, seed=seed, n_iterations=-1)
    return np.array(membership)


# ---------- признаки + сеть: KEFRiN ----------
def modularity_rows(A) -> np.ndarray:
    """Строки модулярностной матрицы B = A − k kᵀ / 2m (плотная, N×N)."""
    A = sp.csr_matrix(A).astype(float)
    k = np.asarray(A.sum(1)).ravel()
    return A.toarray() - np.outer(k, k) / k.sum()


def _sqdist(X, C):
    return ((X ** 2).sum(1)[:, None] + (C ** 2).sum(1)[None, :] - 2 * X @ C.T).clip(min=0)


def _cosdist(X, C):
    Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    Cn = C / np.maximum(np.linalg.norm(C, axis=1, keepdims=True), 1e-12)
    return 1 - Xn @ Cn.T


def kefrin_weights(Y, P):
    """ξ уравнивает суммарный разброс признаков и строк сети (ρ = 1)."""
    ty = ((Y - Y.mean(0)) ** 2).sum()
    tp = ((P - P.mean(0)) ** 2).sum()
    return 1.0, ty / max(tp, 1e-12)


def kefrin(Y, P, K, rho=None, xi=None, metric="euclidean", seed=0, n_init=10, max_iter=100, init_labels=None,
           return_info=False):
    """KEFRiN: Y — признаки N×V (стандартизованы), P — строки сети N×N (например, modularity_rows(A)).

    init_labels — тёплый старт (для эволюционной версии); иначе k-means++ по склейке пространств.
    """
    Y = np.asarray(Y, float)
    P = np.asarray(P, float)
    if rho is None or xi is None:
        rho, xi = kefrin_weights(Y, P)
    dist = _sqdist if metric == "euclidean" else _cosdist
    rng = np.random.default_rng(seed)
    best = (np.inf, None)
    starts = [init_labels] if init_labels is not None else [None] * n_init
    Z = np.hstack([np.sqrt(rho) * Y, np.sqrt(xi) * P])
    for s in starts:
        if s is None:
            y = KMeans(K, n_init=1, random_state=int(rng.integers(1 << 31))).fit_predict(Z)
        else:
            y = np.asarray(s).copy()
        for _ in range(max_iter):
            C = np.stack([Y[y == k].mean(0) if (y == k).any() else Y[rng.integers(len(Y))] for k in range(K)])
            Lm = np.stack([P[y == k].mean(0) if (y == k).any() else P[rng.integers(len(P))] for k in range(K)])
            D = rho * dist(Y, C) + xi * dist(P, Lm)
            y_new = D.argmin(1)
            if np.array_equal(y_new, y):
                break
            y = y_new
        F = D[np.arange(len(y)), y].sum()
        if F < best[0]:
            best = (F, y.copy(), C, Lm)
    if return_info:
        return best[1], {"F": best[0], "C": best[2], "Lambda": best[3], "rho": rho, "xi": xi}
    return best[1]


# ---------- согласование меток во времени ----------
def align_labels(ref, y, K=None):
    """Перенумеровать y так, чтобы максимально совпасть с ref (венгерский алгоритм по таблице пересечений)."""
    K = K or max(ref.max(), y.max()) + 1
    M = np.zeros((K, K))
    np.add.at(M, (y, ref), 1)
    r, c = linear_sum_assignment(-M)
    mp = dict(zip(r, c))
    return np.array([mp.get(v, v) for v in y])


METHODS_FEATURES = {"kmeans": kmeans, "ward": ward, "gmm": gmm}
METHODS_GRAPH = {"spectral": spectral, "leiden": leiden_k}


# ---------- CANUS (Shalileh, IEEE Access 2025): код автора, скачивается scripts/s04_external_code.py ----------
def canus(Y, A, K, seed=0, epochs=300, **kw):
    """Градиентный спуск с фильтрацией обновлений по норме градиента; признаки + строки сети, косинусные расстояния."""
    import sys
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "third_party" / "CANUS"
    if not p.exists():
        raise ImportError("CANUS не скачан: python scripts/s04_external_code.py")
    sys.path.insert(0, str(p))
    from canus import CANUSClusterer
    A = sp.csr_matrix(A).toarray().astype(np.float32) if sp.issparse(A) else np.asarray(A, np.float32)
    m = CANUSClusterer(n_clusters=K, epochs=epochs, seed=seed, device="cpu", **kw)
    m.fit(np.asarray(Y, np.float32), A)
    return m.y_pred
