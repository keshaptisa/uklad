"""Динамика типов: помесячные атрибутированные сети и три способа отследить кластеры во времени.

Помесячная сеть месяца t: узлы — МО; атрибуты Y_t — экономическая база (Росстат, постоянна) + уровень трат месяца t;
рёбра A_t — kNN по косинусному сходству корзины в месяце t (уровень, CLR-структура, остаток Энгеля;
скользящее среднее за 3 месяца, чтобы разовые всплески не рвали связи).

Способы отслеживания:
1. independent — KEFRiN отдельно на каждом месяце, метки сопоставляются с прошлым месяцем венгерским алгоритмом;
2. evolutionary — эволюционная кластеризация (Chakrabarti, Kumar, Tomkins, KDD 2006): кластеризуем сглаженный срез
   Ỹ_t = α·Ỹ_{t−1} + (1−α)·Y_t,  P̃_t = α·P̃_{t−1} + (1−α)·P_t  с тёплым стартом от меток t−1.
   α — вес истории: 0 = без памяти, ближе к 1 = типы меняются медленно;
2a. affect — то же, но α_t оценивается из данных в каждом месяце (AFFECT: Xu, Kliger, Hero, DMKD 2014).
   Сглаженный срез — оценка с усадкой к истории; оптимальный вес истории
       α_t* = Σ var(W_t) / ( Σ var(W_t) + Σ (Ψ_{t−1} − E[W_t])² ),
   где E[W_t] и var(W_t) оцениваются по кластерам прошлого месяца (внутри типа МО считаются однородными).
   Шум в данных месяца велик по сравнению со сдвигом от истории → α_t ближе к 1 (памяти больше), и наоборот;
3. temporal_leiden — многослойная модулярность (Mucha et al., Science 2010), только сеть.

Переход МО считаем устойчивым, если новый тип держится ≥ min_run месяцев (иначе — шум/сезонность).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import adjusted_mutual_info_score as AMI

from . import partition as C
from . import network as G
from . import attributes as F


def monthly_inputs(design, k: int, smooth: int = 3):
    """Списки Y_t (N×V, стандартизованы по всей панели) и A_t (kNN по корзине месяца t)."""
    mf = design.monthly
    cons = ["level"] + [f"clr_{p}" for p in F.PARTS] + ["engel"]
    # скользящее среднее назад (для первых месяцев — по доступным)
    sm = mf[cons].groupby(level=0, group_keys=False).apply(lambda g: g.rolling(smooth, min_periods=1).mean())
    z = (sm - sm.mean()) / sm.std()
    months = sorted(mf.index.get_level_values(1).unique())
    ctx_cols = [c for c in design.Y.columns if c != "level"]
    lvl_mu, lvl_sd = sm["level"].mean(), sm["level"].std()
    Ys, As = [], []
    for m in months:
        zm = z.xs(m, level=1).loc[design.ids]
        Y = design.Y[ctx_cols].copy()
        if "level" in design.Y.columns:
            Y["level"] = ((sm["level"].xs(m, level=1).loc[design.ids] - lvl_mu) / lvl_sd).clip(-4, 4).values
        Ys.append(Y[design.Y.columns].values)
        As.append(G.knn_graph(G.cosine_sim(zm.values), k))
    return months, Ys, As


def evolutionary_kefrin(Ys, As, K, alpha, init_labels, rho, xi, seed=0, metric="euclidean"):
    labels, Ysm, Psm = [], None, None
    prev = init_labels
    for Y, A in zip(Ys, As):
        P = C.modularity_rows(A)
        Ysm = Y if Ysm is None else alpha * Ysm + (1 - alpha) * Y
        Psm = P if Psm is None else alpha * Psm + (1 - alpha) * P
        y = C.kefrin(Ysm, Psm, K, rho=rho, xi=xi, init_labels=prev, seed=seed, metric=metric)
        y = C.align_labels(prev, y, K)
        labels.append(y)
        prev = y
    return np.array(labels)


def affect_alpha(prev, cur, labels, lo=0.0, hi=0.95):
    """Оптимальный вес истории AFFECT: усадка текущего среза cur к сглаженному prev; блоки — кластеры labels."""
    num = den = 0.0
    for k in np.unique(labels):
        m = labels == k
        if m.sum() < 2:
            continue
        mu = cur[m].mean(0)
        v = cur[m].var(0, ddof=1).sum() * m.sum()
        num += v
        den += v + ((prev[m] - mu) ** 2).sum()
    return float(np.clip(num / den if den > 0 else 0.0, lo, hi))


def affect_kefrin(Ys, As, K, init_labels, rho, xi, seed=0, metric="euclidean"):
    """Эволюционный KEFRiN с адаптивным α_t (AFFECT). Возвращает метки T × N и ряд α_t."""
    labels, alphas, Ysm, Psm = [], [], None, None
    prev = init_labels
    for Y, A in zip(Ys, As):
        P = C.modularity_rows(A)
        if Ysm is None:
            a = 0.0
            Ysm, Psm = Y, P
        else:
            # одна α на оба пространства: признаки и строки сети взвешены как в KEFRiN (ρ, ξ)
            Zp = np.hstack([np.sqrt(rho) * Ysm, np.sqrt(xi) * Psm])
            Zc = np.hstack([np.sqrt(rho) * Y, np.sqrt(xi) * P])
            a = affect_alpha(Zp, Zc, prev)
            Ysm, Psm = a * Ysm + (1 - a) * Y, a * Psm + (1 - a) * P
        y = C.kefrin(Ysm, Psm, K, rho=rho, xi=xi, init_labels=prev, seed=seed, metric=metric)
        y = C.align_labels(prev, y, K)
        labels.append(y)
        alphas.append(a)
        prev = y
    return np.array(labels), np.array(alphas)


def independent_kefrin(Ys, As, K, init_labels, rho, xi, seed=0, metric="euclidean"):
    labels, prev = [], init_labels
    for Y, A in zip(Ys, As):
        y = C.kefrin(Y, C.modularity_rows(A), K, rho=rho, xi=xi, seed=seed, n_init=5, metric=metric)
        y = C.align_labels(prev, y, K)
        labels.append(y)
        prev = y
    return np.array(labels)


def persistent_switches(L: np.ndarray, min_run: int = 3) -> pd.DataFrame:
    """Устойчивые переходы: тип до и после держится ≥ min_run месяцев подряд. L: T × N."""
    T, N = L.shape
    rows = []
    for i in range(N):
        s = L[:, i]
        runs, start = [], 0
        for t in range(1, T + 1):
            if t == T or s[t] != s[start]:
                runs.append((start, t - 1, s[start]))
                start = t
        long = [r for r in runs if r[1] - r[0] + 1 >= min_run]
        for a, b in zip(long, long[1:]):
            if a[2] != b[2]:
                rows.append({"i": i, "from": int(a[2]), "to": int(b[2]), "t_switch": b[0]})
    return pd.DataFrame(rows, columns=["i", "from", "to", "t_switch"])


def dynamics_summary(L: np.ndarray, min_run: int = 3) -> dict:
    T, N = L.shape
    switches = (L[1:] != L[:-1]).sum(1)
    ps = persistent_switches(L, min_run)
    return {
        "AMI_adjacent": float(np.mean([AMI(L[t], L[t + 1]) for t in range(T - 1)])),
        "switch_rate_month": float(switches.mean() / N),
        "never_switch": float((L == L[0]).all(0).mean()),
        "persistent_switches": len(ps),
        "persistent_share_of_all": len(ps) / max(int(switches.sum()), 1),
    }


def transition_matrix(L: np.ndarray, K: int) -> np.ndarray:
    M = np.zeros((K, K))
    for t in range(len(L) - 1):
        np.add.at(M, (L[t], L[t + 1]), 1)
    return M / M.sum(1, keepdims=True)


def monic_events(L0, L1, tau=0.5, tau_split=0.25):
    """События MONIC (Spiliopoulou et al., KDD 2006) между двумя разбиениями: выживание, распад, поглощение, исчезновение, появление."""
    ev = []
    k0, k1 = np.unique(L0), np.unique(L1)
    for a in k0:
        X = L0 == a
        ov = {b: (X & (L1 == b)).sum() / X.sum() for b in k1}
        best = max(ov, key=ov.get)
        if ov[best] >= tau:
            ev.append(("выживание", int(a), int(best), round(ov[best], 3)))
        else:
            parts = {b: v for b, v in ov.items() if v >= tau_split}
            if sum(parts.values()) >= tau and len(parts) > 1:
                ev.append(("распад", int(a), str(sorted(int(b) for b in parts)), round(sum(parts.values()), 3)))
            else:
                ev.append(("исчезновение", int(a), None, round(ov[best], 3)))
    for b in k1:
        Yb = L1 == b
        src = {a: (Yb & (L0 == a)).sum() / (L0 == a).sum() for a in k0}
        absorbed = [a for a, v in src.items() if v >= tau]
        if len(absorbed) > 1:
            ev.append(("поглощение", str(sorted(int(a) for a in absorbed)), int(b), None))
        if not any((Yb & (L0 == a)).sum() / Yb.sum() >= tau for a in k0) and not absorbed:
            ev.append(("появление", None, int(b), None))
    return pd.DataFrame(ev, columns=["event", "from", "to", "overlap"])
