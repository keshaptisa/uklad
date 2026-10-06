"""Правила ребра между МО и разрежение до kNN-графа.

Каждое правило даёт матрицу сходства S (N×N, больше — ближе). Граф: каждый МО связан с k самыми
похожими (kNN), затем симметризация. Вес ребра — сходство, приведённое к [0, 1].

Правила (все — из перечня в задании):
- cosine: косинус между векторами признаков (структура и уровень трат) — «тратят одинаково»;
- corr: корреляция Пирсона месячных рядов отклонений от общероссийской динамики — «движутся вместе»;
- lagcorr: максимум корреляции по сдвигам ±L месяцев — «один МО опережает другой»;
- dtw: динамическое выравнивание рядов (DTW) с окном Сакоэ–Тибы — «одинаковая форма траектории с допуском по времени»;
- road: близость по автодорогам, exp(−d/d0) — «соседи»;
- rbf: гауссово ядро по евклидову расстоянию с локальным масштабом (Zelnik-Manor & Perona 2004).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp


def knn_graph(S: np.ndarray, k: int, mutual: bool = False) -> sp.csr_matrix:
    """kNN-разрежение матрицы сходства. mutual=False — объединение (ребро, если j в соседях i или i в соседях j)."""
    S = np.array(S, dtype=float, copy=True)
    np.fill_diagonal(S, -np.inf)
    n = S.shape[0]
    idx = np.argpartition(-S, k, axis=1)[:, :k]
    rows = np.repeat(np.arange(n), k)
    cols = idx.ravel()
    w = S[rows, cols]
    M = sp.csr_matrix((np.ones_like(w), (rows, cols)), shape=(n, n))
    keep = M.multiply(M.T) if mutual else M.maximum(M.T)
    S[np.isinf(S)] = 0
    lo = np.nanmin(S[keep.nonzero()]) if keep.nnz else 0
    hi = np.nanmax(S[keep.nonzero()]) if keep.nnz else 1
    W = keep.multiply(sp.csr_matrix((S - lo) / (hi - lo + 1e-12) * 0.99 + 0.01))
    W = sp.csr_matrix(W)
    W.setdiag(0)
    W.eliminate_zeros()
    return W


def cosine_sim(X: np.ndarray) -> np.ndarray:
    Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    return Xn @ Xn.T


def corr_sim(T: np.ndarray) -> np.ndarray:
    """T: N × time (или N × time·каналы, каналы уже стандартизованы). Корреляция Пирсона строк."""
    Tc = T - T.mean(axis=1, keepdims=True)
    return cosine_sim(Tc)


def lagcorr_sim(T: np.ndarray, max_lag: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Максимум корреляции по сдвигам −L..L для одноканальных рядов T (N × time). Возвращает (S, лаг)."""
    n, L = T.shape
    best = np.full((n, n), -np.inf)
    lag = np.zeros((n, n), dtype=int)
    for s in range(-max_lag, max_lag + 1):
        a = T[:, max(0, s):L + min(0, s)]
        b = T[:, max(0, -s):L - max(0, s)]
        c = cosine_sim(a - a.mean(1, keepdims=True)).copy() if s == 0 else _cross_corr(a, b)
        upd = c > best
        best[upd] = c[upd]
        lag[upd] = s
    return best, lag


def _cross_corr(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """corr(a_i(t), b_j(t)) для всех пар: a — ряд i со сдвигом, b — ряд j."""
    a = a - a.mean(1, keepdims=True)
    b = b - b.mean(1, keepdims=True)
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return a @ b.T


def dtw_dist(T: np.ndarray, window: int = 2, chunk: int = 128) -> np.ndarray:
    """Попарное DTW-расстояние (окно Сакоэ–Тибы). T: N × time × channels. Векторизовано по парам, O(N²·time·window)."""
    if T.ndim == 2:
        T = T[:, :, None]
    n, L, _ = T.shape
    D = np.zeros((n, n), dtype=np.float32)
    T = T.astype(np.float32)
    INF = np.float32(np.inf)
    for i0 in range(0, n, chunk):
        A = T[i0:i0 + chunk]                                   # c × L × ch
        c = A.shape[0]
        prev = np.full((L + 1, c, n), INF, dtype=np.float32)   # строка t−1 таблицы накопленной стоимости
        prev[0] = 0
        for t in range(1, L + 1):
            cur = np.full((L + 1, c, n), INF, dtype=np.float32)
            for u in range(max(1, t - window), min(L, t + window) + 1):
                cost = np.sqrt(((A[:, t - 1, None, :] - T[None, :, u - 1, :]) ** 2).sum(-1))
                cur[u] = cost + np.minimum(np.minimum(prev[u], cur[u - 1]), prev[u - 1])
            prev = cur
        D[i0:i0 + chunk] = prev[L]
    return np.maximum(D, D.T)


def rbf_sim(X: np.ndarray, k_scale: int = 7) -> np.ndarray:
    """Самонастраивающееся гауссово ядро: exp(−d²/(σ_i σ_j)), σ_i — расстояние до k-го соседа."""
    sq = (X ** 2).sum(1)
    d2 = np.maximum(sq[:, None] + sq[None, :] - 2 * X @ X.T, 0)
    d = np.sqrt(d2)
    sig = np.sort(d, axis=1)[:, k_scale]
    return np.exp(-d2 / np.maximum(np.outer(sig, sig), 1e-12))


def road_distance(ids: np.ndarray, connection: pd.DataFrame, kind: str = "highway") -> np.ndarray:
    """Матрица дорожных расстояний между МО (км); пары без пути — бесконечность."""
    pos = pd.Series(np.arange(len(ids)), index=ids)
    c = connection[(connection.type == kind)
                   & connection.territory_id_x.isin(ids) & connection.territory_id_y.isin(ids)]
    D = np.full((len(ids), len(ids)), np.inf, dtype=np.float32)
    i = pos[c.territory_id_x.values].values
    j = pos[c.territory_id_y.values].values
    D[i, j] = c.distance.values
    D[j, i] = np.minimum(D[j, i], c.distance.values)
    np.fill_diagonal(D, 0)
    return D


def road_sim(D: np.ndarray, d0: float = 200.0) -> np.ndarray:
    return np.exp(-D / d0)


def edge_jaccard(A: sp.spmatrix, B: sp.spmatrix) -> float:
    a = set(zip(*sp.triu(A, 1).nonzero()))
    b = set(zip(*sp.triu(B, 1).nonzero()))
    return len(a & b) / max(len(a | b), 1)


def _snf_affinity(D: np.ndarray, K: int = 20, mu: float = 0.5) -> np.ndarray:
    """Ядро SNF с локальным масштабом: ε_ij = (средн. расстояние i и j до K соседей + d_ij) / 3."""
    D = (D + D.T) / 2
    Ds = np.sort(D, 1)[:, 1:K + 1].mean(1)
    eps = (Ds[:, None] + Ds[None, :] + D) / 3 + 1e-12
    W = np.exp(-D ** 2 / (mu * eps))
    return (W + W.T) / 2


def _snf_full(W):
    W = W.copy()
    np.fill_diagonal(W, 0)
    W = W / (2 * W.sum(1, keepdims=True))
    np.fill_diagonal(W, 0.5)
    return W


def _snf_local(W, K):
    S = np.zeros_like(W)
    idx = np.argsort(-W, 1)[:, :K]
    r = np.arange(len(W))[:, None]
    S[r, idx] = W[r, idx]
    return S / S.sum(1, keepdims=True)


def snf(dists: list[np.ndarray], K: int = 20, mu: float = 0.5, t: int = 20) -> np.ndarray:
    """Similarity Network Fusion (Wang et al., Nature Methods 2014): каждая сеть итеративно диффундирует
    по kNN-структуре остальных, P_v ← S_v · mean(P_u, u≠v) · S_vᵀ. Остаются связи, которые
    поддержаны несколькими взглядами; связь, видная только в одном, затухает."""
    Ws = [_snf_affinity(D, K, mu) for D in dists]
    Ps = [_snf_full(W) for W in Ws]
    Ss = [_snf_local(W, K) for W in Ws]
    for _ in range(t):
        new = []
        for v in range(len(Ps)):
            other = sum(Ps[u] for u in range(len(Ps)) if u != v) / (len(Ps) - 1)
            P = Ss[v] @ other @ Ss[v].T
            new.append(_snf_full((P + P.T) / 2))
        Ps = new
    F = sum(Ps) / len(Ps)
    return (F + F.T) / 2
