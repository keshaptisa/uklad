"""Внутренние индексы качества кластеризации (ICVI) из задания: SW, CH, S_Dbw (признаки) и AVI, AVU, MQ (сеть).

Признаковое пространство:
- SW (силуэт, Rousseeuw 1987), больше — лучше;
- CH (Калински–Харабаш 1974), больше — лучше; растёт на сферических кластерах, поэтому подыгрывает k-means;
- S_Dbw (Halkidi & Vazirgiannis 2001), меньше — лучше: разброс внутри + плотность между кластерами.

Сетевое пространство (Biswas & Biswas 2017; формулы — как в библиотеке Pattern Лаборатории СберИндекс):
S_ab = суммарный вес рёбер между кластерами a и b (внутренние рёбра входят дважды).
- AVI, средняя изолированность: mean_a S_aa / Σ_b S_ab; больше — лучше; у случайного разбиения ≈ 1/K;
- AVU, средняя «слитость»: (1/K) Σ_a Σ_{b≠a} S_ab / (out_a + out_b − S_ab); меньше — лучше;
- ANUI = 1 / (AVU + 1/AVI) — сводный индекс лаборатории, больше — лучше;
- MQ: основная версия — модулярность Q Ньюмана–Гирвана (так метрика называется в коде лаборатории);
  дополнительно MQ_Mancoridis = Σ_a 2μ_a / (2μ_a + Σ_{b≠a}(ε_ab + ε_ba)) — Modularization Quality (1998).

Сравнивать индексы при разном K напрямую нельзя (AVI ~ 1/K), поэтому `icvi_z` даёт z-оценку
против перестановок меток при тех же размерах кластеров.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from sklearn.metrics import calinski_harabasz_score, silhouette_score

HIGHER_IS_BETTER = {"SW": True, "CH": True, "S_Dbw": False, "AVI": True, "AVU": False,
                    "ANUI": True, "MQ": True, "MQ_Mancoridis": True, "MQ_basic": True, "density_modularity": True}


def _relabel(labels) -> tuple[np.ndarray, int]:
    _, y = np.unique(np.asarray(labels), return_inverse=True)
    return y, int(y.max()) + 1


def block_matrix(A, labels) -> np.ndarray:
    """S[a, b] = Σ_{i∈a, j∈b} A_ij для симметричной матрицы смежности без петель."""
    y, K = _relabel(labels)
    H = sp.csr_matrix((np.ones(len(y)), (np.arange(len(y)), y)), shape=(len(y), K))
    A = sp.csr_matrix(A)
    return np.asarray((H.T @ A @ H).todense())


def graph_icvi(A, labels, basic: bool = False) -> dict:
    """Сетевые индексы; basic=True добавляет BasicMQ Манкоридиса (нужен только в проверке рейтинга, s13_checks)."""
    S = block_matrix(A, labels)
    K = S.shape[0]
    tot = S.sum(1)
    d = np.diag(S).copy()
    avi = np.divide(d, tot, out=np.zeros(K), where=tot > 0).mean()
    out = tot - d
    den = out[:, None] + out[None, :] - S
    U = np.divide(S, den, out=np.zeros_like(S), where=den > 0)
    np.fill_diagonal(U, 0)
    avu = U.sum() / K
    anui = 1.0 / (avu + 1.0 / avi) if avi > 0 else 0.0
    two_m = S.sum()
    q = float((d / two_m - (tot / two_m) ** 2).sum()) if two_m > 0 else 0.0
    # Mancoridis: 2μ_a = S_aa, межкластерные рёбра в обе стороны = out_a
    mq_m = float(np.divide(d, d + out, out=np.zeros(K), where=(d + out) > 0).sum())
    # density modularity — дополнительный индекс из библиотеки Pattern
    sizes = np.bincount(_relabel(labels)[0], minlength=K)
    dmod = float(((d / 2 - tot ** 2 / (2 * two_m)) / np.maximum(sizes, 1)).sum()) if two_m > 0 else 0.0
    # BasicMQ (Mancoridis et al., 1998): связность внутри A_i = μ_i / N_i² минус связность между E_ij = ε_ij / (2·N_i·N_j);
    # в отличие от TurboMQ (на неориентированном графе = K·AVI) штрафует межкластерные связи и учитывает размеры типов
    n = np.maximum(sizes, 1).astype(float)
    intra = (d / 2) / n ** 2
    inter = np.triu(S, 1) / (2 * np.outer(n, n))
    mq_b = float(intra.mean() - (inter.sum() / (K * (K - 1) / 2) if K > 1 else 0.0))
    out = {"AVI": float(avi), "AVU": float(avu), "ANUI": float(anui), "MQ": q, "MQ_Mancoridis": mq_m,
           "density_modularity": dmod}
    if basic:
        out["MQ_basic"] = mq_b
    return out


def sdbw(X, labels) -> float:
    """S_Dbw по Halkidi & Vazirgiannis (ICDM 2001).

    Scat = (1/K) Σ_k ‖σ(C_k)‖ / ‖σ(X)‖, где σ — вектор дисперсий признаков;
    stdev = (1/K)·sqrt(Σ_k ‖σ(C_k)‖); density(u) — число точек C_k ∪ C_l в шаре радиуса stdev вокруг u;
    Dens_bw = 1/(K(K−1)) Σ_{k≠l} density(u_kl) / max(density(v_k), density(v_l)), u_kl — середина центров.
    Своя реализация: пакет s-dbw падает, когда у двух кластеров плотность в центре нулевая.
    """
    X = np.asarray(X, dtype=float)
    y, K = _relabel(labels)
    cents = np.stack([X[y == k].mean(0) for k in range(K)])
    sig = np.stack([X[y == k].var(0) for k in range(K)])
    norms = np.linalg.norm(sig, axis=1)
    scat = norms.mean() / np.linalg.norm(X.var(0))
    stdev = np.sqrt(norms.sum()) / K

    def density(u, mask):
        return int((np.linalg.norm(X[mask] - u, axis=1) <= stdev).sum())

    dens = 0.0
    for k in range(K):
        for l in range(K):
            if k == l:
                continue
            m = (y == k) | (y == l)
            dk, dl = density(cents[k], m), density(cents[l], m)
            mx = max(dk, dl)
            if mx > 0:
                dens += density((cents[k] + cents[l]) / 2, m) / mx
    return float(scat + dens / (K * (K - 1)))


def feature_icvi(X, labels, sample: int | None = None, seed: int = 0) -> dict:
    X = np.asarray(X, dtype=float)
    y, K = _relabel(labels)
    if K < 2:
        return {"SW": np.nan, "CH": np.nan, "S_Dbw": np.nan}
    sw = silhouette_score(X, y, sample_size=sample, random_state=seed) if sample else silhouette_score(X, y)
    return {"SW": float(sw), "CH": float(calinski_harabasz_score(X, y)), "S_Dbw": sdbw(X, y)}


def icvi(X, A, labels) -> dict:
    return {**feature_icvi(X, labels), **graph_icvi(A, labels)}


def icvi_z(X, A, labels, n_perm: int = 50, seed: int = 0) -> dict:
    """z-оценка каждого индекса против случайной перестановки меток (размеры кластеров те же).

    Знак приведён так, что больше z — всегда лучше (для S_Dbw и AVU знак обращён).
    """
    rng = np.random.default_rng(seed)
    obs = icvi(X, A, labels)
    perms = [icvi(X, A, rng.permutation(labels)) for _ in range(n_perm)]
    z = {}
    for k, v in obs.items():
        vals = np.array([p[k] for p in perms])
        sd = vals.std(ddof=1)
        zz = (v - vals.mean()) / sd if sd > 0 else np.nan
        z[k] = zz if HIGHER_IS_BETTER[k] else -zz
    return z
