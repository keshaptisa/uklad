"""Сведение нескольких критериев качества в один рейтинг методов.

Пороговое агрегирование (Aleskerov, Yakuba, Yuzbashev, Math. Social Sciences 2007): каждый критерий ставит методу
оценку 1/2/3 (лучшая, средняя, худшая треть). Лучше тот метод, у которого меньше «троек»; при равенстве — меньше «двоек».
Метод не компенсирует провал по одному критерию успехом по другому — в отличие от суммы баллов.
Для сравнения рядом даём правило Борда (сумма мест).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def three_grades(scores: pd.Series) -> pd.Series:
    """Оценки 1/2/3 по трети мест (больше score — лучше)."""
    r = scores.rank(ascending=False, method="min")
    n = scores.notna().sum()
    g = np.where(r <= np.ceil(n / 3), 1, np.where(r <= np.ceil(2 * n / 3), 2, 3))
    return pd.Series(g, index=scores.index).where(scores.notna(), 3)


def threshold_aggregation(Z: pd.DataFrame) -> pd.DataFrame:
    """Z: методы × критерии (больше — лучше). Возвращает оценки, число 1/2/3 и итоговое место."""
    G = Z.apply(three_grades)
    out = G.copy()
    out["n1"], out["n2"], out["n3"] = (G == 1).sum(axis=1), (G == 2).sum(axis=1), (G == 3).sum(axis=1)
    key = out["n3"] * 100 + out["n2"]          # меньше троек, затем меньше двоек
    out["rank_threshold"] = key.rank(method="min").astype(int)
    out["borda"] = Z.rank(ascending=True).sum(axis=1)  # больше — лучше
    out["rank_borda"] = out["borda"].rank(ascending=False, method="min").astype(int)
    return out.sort_values(["rank_threshold", "rank_borda"])


def copeland(Z: pd.DataFrame) -> pd.DataFrame:
    """Правило Коупленда: метод a побеждает b, если лучше по большинству критериев; счёт = победы − поражения.

    Как и пороговое агрегирование, не складывает величины критериев, а только сравнивает методы попарно.
    """
    n = len(Z)
    V = Z.values
    score = np.zeros(n)
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            wins = np.nansum(V[a] > V[b]) - np.nansum(V[a] < V[b])
            score[a] += np.sign(wins)
    out = pd.DataFrame({"copeland": score}, index=Z.index)
    out["rank_copeland"] = out["copeland"].rank(ascending=False, method="min").astype(int)
    return out.sort_values("rank_copeland")
