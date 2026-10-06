"""Интерпретация типов: профиль по Миркину, описания понятиями FCA, паттерны Алескерова–Мячина, внешняя проверка.

- Профиль по Миркину (теория восстановления данных; Mirkin 2012, Alvandyan & Shalileh 2024):
  отклонение центра типа от среднего по стране в % и вклад пары «тип × признак» в объяснённый разброс
  B_kv = |S_k|·(c_kv − ȳ_v)² / T на стандартизованных признаках.
- FCA (Ganter & Wille 1999; устойчивость понятия — Kuznetsov 2007): признаки шкалируются в бинарные
  («зарплата: верхняя четверть»), для каждого типа жадно ищется содержание B с высокой точностью |A∩S_k|/|A|,
  проверяется замкнутость (B'' = B) и оценивается устойчивость σ методом Монте-Карло.
- OIPC — порядково-инвариантная паттерн-кластеризация (Мячин 2019; Алескеров и др. 2013): два МО в одном паттерне,
  если у них одинаковый порядок нормированных показателей. Число паттернов не задаётся заранее.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd


# ---------- Миркин ----------
def mirkin_profile(raw: pd.DataFrame, Z: pd.DataFrame, y: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(отклонение среднего типа от среднего по стране в %, доля вклада B_kv в общий разброс в %)."""
    mean_all = raw.mean()
    dev = (raw.groupby(y).mean() - mean_all) / mean_all.abs() * 100
    T = ((Z - Z.mean()) ** 2).values.sum()
    sizes = pd.Series(y).value_counts().sort_index()
    cz = Z.groupby(y).mean() - Z.mean()
    contrib = cz ** 2 * sizes.values[:, None] / T * 100
    return dev, contrib


# ---------- FCA ----------
def scale_context(raw: pd.DataFrame, extra: pd.DataFrame | None = None) -> pd.DataFrame:
    """Номинальное шкалирование: для каждого показателя — «низкий» (нижняя четверть) и «высокий» (верхняя четверть),
    плюс «ниже медианы»/«выше медианы». Бинарные столбцы extra добавляются как есть."""
    cols = {}
    for c in raw.columns:
        v = raw[c]
        q1, q2, q3 = v.quantile([0.25, 0.5, 0.75])
        cols[f"{c}: нижняя четверть"] = v <= q1
        cols[f"{c}: ниже медианы"] = v <= q2
        cols[f"{c}: выше медианы"] = v > q2
        cols[f"{c}: верхняя четверть"] = v > q3
    M = pd.DataFrame(cols, index=raw.index)
    if extra is not None:
        M = M.join(extra.astype(bool))
    return M


def _extent(M: np.ndarray, attrs) -> np.ndarray:
    return M[:, list(attrs)].all(1) if len(attrs) else np.ones(M.shape[0], bool)


def _intent(M: np.ndarray, ext: np.ndarray) -> list[int]:
    return list(np.where(M[ext].all(0))[0]) if ext.any() else list(range(M.shape[1]))


def stability(M: np.ndarray, ext: np.ndarray, intent: list[int], n_samples=300, rng=None) -> float:
    """Устойчивость понятия по Кузнецову: доля подмножеств объёма, сохраняющих то же содержание (оценка Монте-Карло)."""
    rng = rng or np.random.default_rng(0)
    objs = np.where(ext)[0]
    keep = 0
    for _ in range(n_samples):
        sub = objs[rng.random(len(objs)) < 0.5]
        if len(sub) == 0:
            continue
        if set(np.where(M[sub].all(0))[0]) == set(intent):
            keep += 1
    return keep / n_samples


def fca_describe(Mdf: pd.DataFrame, y: np.ndarray, k: int, max_len=3, min_cover=0.2, n_best=3, rng=None) -> list[dict]:
    """Лучшие понятия для типа k: жадный поиск содержания по точности при покрытии ≥ min_cover, затем замыкание."""
    M = Mdf.values.astype(bool)
    names = list(Mdf.columns)
    target = y == k
    res = []
    cand = [(a,) for a in range(M.shape[1])]
    beam = []
    for L in range(1, max_len + 1):
        scored = []
        for attrs in cand:
            ext = _extent(M, attrs)
            if ext.sum() == 0:
                continue
            prec = (ext & target).sum() / ext.sum()
            cover = (ext & target).sum() / target.sum()
            if cover >= min_cover:
                scored.append((prec, cover, attrs))
        scored.sort(key=lambda s: (-s[0], -s[1]))
        beam = scored[:25]
        res.extend(beam)
        cand = list({tuple(sorted(set(b[2]) | {a})) for b in beam for a in range(M.shape[1]) if a not in b[2]})
    # убираем дубли по объёму, берём лучшие по точности, затем по покрытию
    seen, out = set(), []
    for prec, cover, attrs in sorted(res, key=lambda s: (-round(s[0], 2), -s[1], len(s[2]))):
        ext = _extent(M, attrs)
        key = ext.tobytes()
        if key in seen:
            continue
        seen.add(key)
        intent = _intent(M, ext)  # замыкание: всё общее у объектов объёма
        out.append({"type": k, "description": " И ".join(names[a] for a in attrs),
                    "closure_size": len(intent), "precision": prec, "coverage": cover, "extent": int(ext.sum()),
                    "stability": stability(M, ext, intent, rng=rng)})
        if len(out) >= n_best:
            break
    return out


# ---------- OIPC (Алескеров–Мячин) ----------
def oipc(X: pd.DataFrame, eps: float = 0.0) -> pd.Series:
    """Паттерн МО — знаки попарных сравнений нормированных показателей (>, =, <). eps — допуск равенства."""
    V = X.values
    pairs = list(itertools.combinations(range(V.shape[1]), 2))
    S = np.stack([np.sign(np.where(np.abs(V[:, a] - V[:, b]) <= eps, 0, V[:, a] - V[:, b])) for a, b in pairs], 1)
    _, lab = np.unique(S, axis=0, return_inverse=True)
    return pd.Series(lab.ravel(), index=X.index)


def pattern_name(X: pd.DataFrame, members: pd.Index) -> str:
    """Порядок показателей в паттерне: «a > b > c» по средним нормированным значениям."""
    m = X.loc[members].mean().sort_values(ascending=False)
    return " > ".join(m.index)


# ---------- внешняя проверка ----------
def eta_squared(v: pd.Series, y: np.ndarray) -> float:
    """Доля дисперсии показателя, объяснённая типами (корреляционное отношение η²)."""
    v = pd.Series(np.asarray(v, float))
    ok = v.notna().values
    v, yy = v[ok], np.asarray(y)[ok]
    grand = v.mean()
    between = sum(((v[yy == k].mean() - grand) ** 2) * (yy == k).sum() for k in np.unique(yy))
    total = ((v - grand) ** 2).sum()
    return float(between / total) if total > 0 else np.nan
