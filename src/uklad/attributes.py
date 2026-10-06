"""Признаки МО. Четыре блока — четыре вопроса о локальной экономике.

- level («Сколько тратят»): логарифм трат на жителя минус медиана по всем МО в том же месяце.
  Снимает общероссийскую инфляцию и сезонность, остаётся относительный уровень.
- structure («На что тратят»): CLR-координаты долей шести частей корзины (продовольствие, здоровье,
  маркетплейсы, общепит, транспорт, прочее). Доли в сумме дают 1, поэтому обычные расстояния между ними
  искажены; CLR (центрированный логарифм отношения, геометрия Айчисона) это исправляет.
- engel: отклонение доли продовольствия от общероссийской кривой Энгеля (доля еды падает с ростом трат).
  Положительное значение — «на еду уходит больше, чем положено при таком уровне трат».
- rhythm («Когда тратят»): сезонный профиль за вычетом общероссийского месяца и собственного тренда МО.
- context («Чем живут», Росстат + СберИндекс): зарплата, население, урбанизация, структура занятости, доступность рынков.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PARTS = ["food", "health", "market", "cafe", "transport", "other"]
CONTEXT = ["log_wage", "log_pop", "urban_share", "log_market_access",
           "emp_agro", "emp_mining", "emp_industry", "emp_transport", "emp_market_services", "emp_public"]


def spend_cube(spend: pd.DataFrame) -> pd.DataFrame:
    """Широкая таблица: индекс (territory_id, month), столбцы — категории, плюс «прочее» = всё − пять категорий."""
    w = spend.pivot_table(index=["territory_id", "month"], columns="category", values="value").sort_index()
    named = ["food", "health", "market", "cafe", "transport"]
    # прочее не может быть меньше 2% от всех трат: в редких МО сумма пяти категорий чуть больше итога (округления модели)
    w["other"] = np.maximum(w["total"] - w[named].sum(axis=1), 0.02 * w["total"])
    return w


def shares(w: pd.DataFrame) -> pd.DataFrame:
    s = w[PARTS]
    return s.div(s.sum(axis=1), axis=0)


def clr(s: pd.DataFrame) -> pd.DataFrame:
    ls = np.log(s)
    return ls.sub(ls.mean(axis=1), axis=0).add_prefix("clr_")


def rel_level(w: pd.DataFrame) -> pd.Series:
    lt = np.log(w["total"])
    return (lt - lt.groupby(level="month").transform("median")).rename("level")


def engel_residual(sh: pd.DataFrame, lvl: pd.Series) -> pd.Series:
    """Остаток доли продовольствия от кривой Энгеля, оценённой по каждому месяцу: food_share ~ a_t + b_t·level."""
    out = pd.Series(index=sh.index, dtype=float, name="engel")
    for m, idx in sh.groupby(level="month").groups.items():
        y = sh.loc[idx, "food"].values
        x = lvl.loc[idx].values
        b, a = np.polyfit(x, y, 1)
        out.loc[idx] = y - (a + b * x)
    return out


def monthly_features(spend: pd.DataFrame) -> pd.DataFrame:
    """Признаки МО по месяцам: уровень, CLR структуры, остаток Энгеля. Индекс (territory_id, month)."""
    w = spend_cube(spend)
    sh = shares(w)
    lvl = rel_level(w)
    f = pd.concat([lvl, clr(sh), engel_residual(sh, lvl)], axis=1)
    return f


def rhythm(spend: pd.DataFrame, cats=("total", "food", "cafe", "transport")) -> pd.DataFrame:
    """Сезонный ритм МО: 12 месяцев × категории.

    log(траты) − медиана по МО в том же месяце (снимает общероссийскую сезонность и инфляцию) →
    − линейный тренд МО (иначе разная скорость роста выглядит как сезонность) → среднее двух лет по календарному месяцу.
    Возвращает таблицу territory_id × (категория, месяц 1..12) и повторяемость ритма между годами.
    """
    w = spend_cube(spend)
    out, rep = {}, {}
    months = w.index.get_level_values("month").unique().sort_values()
    t = np.arange(len(months), dtype=float)
    for c in cats:
        L = np.log(w[c]).unstack("month")[months]
        R = L - L.median(axis=0)
        # снимаем тренд МО по МНК
        tc = t - t.mean()
        slope = (R.values * tc).sum(axis=1) / (tc ** 2).sum()
        D = R.values - R.values.mean(axis=1, keepdims=True) - np.outer(slope, tc)
        y1, y2 = D[:, :12], D[:, 12:24]
        prof = (y1 + y2) / 2
        for k in range(12):
            out[(c, k + 1)] = prof[:, k]
        num = ((y1 - y1.mean(1, keepdims=True)) * (y2 - y2.mean(1, keepdims=True))).sum(1)
        den = np.sqrt(((y1 - y1.mean(1, keepdims=True)) ** 2).sum(1) * ((y2 - y2.mean(1, keepdims=True)) ** 2).sum(1))
        rep[c] = num / np.where(den > 0, den, np.nan)
    prof = pd.DataFrame(out, index=L.index)
    prof.columns = pd.MultiIndex.from_tuples(prof.columns, names=["category", "cal_month"])
    return prof, pd.DataFrame(rep, index=L.index)


def context(mo: pd.DataFrame) -> pd.DataFrame:
    c = pd.DataFrame(index=mo.index)
    c["log_wage"] = np.log(mo["wage"])
    c["log_pop"] = np.log(mo["population"])
    c["urban_share"] = mo["urban_share"]
    c["log_market_access"] = np.log(mo["market_access"])
    for k in ["emp_agro", "emp_mining", "emp_industry", "emp_transport", "emp_market_services", "emp_public"]:
        c[k] = mo[k]
    # пропуски (≤1% МО): медиана по региону, иначе по стране
    reg = mo["region_name"]
    c = c.groupby(reg).transform(lambda s: s.fillna(s.median())).fillna(c.median())
    return c[CONTEXT]


def standardize(X: pd.DataFrame, clip: float = 4.0) -> pd.DataFrame:
    """z-оценки по столбцам с обрезкой хвостов: иначе редкие МО (добыча, Москва) доминируют в расстояниях."""
    Z = (X - X.mean()) / X.std(ddof=0).replace(0, 1)
    return Z.clip(-clip, clip)
