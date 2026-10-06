"""Шаг 6. Линза ритма: у каких МО свой сезонный ритм трат и какие типы ритма бывают.

Ритм МО = помесячные траты за вычетом общероссийского месяца и собственного тренда (features.rhythm).
Ритм признаём «своим», если он повторяется: корреляция профилей 2023 и 2024 гг. выше 95-го перцентиля
перестановочного нуля (тот же расчёт для случайных пар «2023 одного МО — 2024 другого») и амплитуда выше медианы.
Такие МО группируем k-means по нормированному 12-месячному профилю (все траты, общепит, продовольствие, транспорт).

Выход: outputs/rhythm/{mo_rhythm.csv, types.csv, profiles.csv}
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import attributes as F  # noqa: E402

cfg = load_config()
rc = cfg["rhythm"]
P = ROOT / cfg["paths"]["processed"]
out = ROOT / cfg["paths"]["outputs"] / "rhythm"
out.mkdir(parents=True, exist_ok=True)
spend = pd.read_parquet(P / "spend.parquet")
mo = pd.read_parquet(P / "mo.parquet")
cats = tuple(rc["categories"])
prof, rep = F.rhythm(spend, cats)
mo = mo.loc[prof.index]

# повторяемость ритма «всех трат» и общепита (самая сезонная категория); перестановочный ноль
w = F.spend_cube(spend)
rng = np.random.default_rng(cfg["seed"])


def null_rep(cat, n=20000):
    L = np.log(w[cat]).unstack("month")
    R = L - L.median(axis=0)
    t = np.arange(R.shape[1]) - (R.shape[1] - 1) / 2
    slope = (R.values * t).sum(1) / (t ** 2).sum()
    D = R.values - R.values.mean(1, keepdims=True) - np.outer(slope, t)
    a, b = rng.integers(len(D), size=n), rng.integers(len(D), size=n)
    y1, y2 = D[a, :12], D[b, 12:24]
    y1 = y1 - y1.mean(1, keepdims=True); y2 = y2 - y2.mean(1, keepdims=True)
    return (y1 * y2).sum(1) / np.sqrt((y1 ** 2).sum(1) * (y2 ** 2).sum(1))


thr = {c: np.quantile(null_rep(c), 0.95) for c in ["total", "cafe"]}
amp = pd.DataFrame({c: prof[c].std(axis=1) for c in cats})
own = ((rep["total"] > thr["total"]) & (amp["total"] > amp["total"].median())) | \
      ((rep["cafe"] > thr["cafe"]) & (amp["cafe"] > amp["cafe"].median()))
print(f"порог повторяемости (95% нуля): {thr}; МО со своим ритмом: {own.sum()} из {len(own)}")

# профиль для кластеризации: каждая категория делится на свою типичную амплитуду, чтобы общепит не доминировал
Xr = pd.concat([prof[c] / amp[c].median() for c in cats], axis=1)
Xo = Xr[own.values]
best = None
for K in range(rc["K_range"][0], rc["K_range"][1] + 1):
    lab = KMeans(K, n_init=30, random_state=cfg["seed"]).fit_predict(Xo)
    s = silhouette_score(Xo, lab)
    print("K", K, "SW", round(s, 3), "размеры", sorted(np.bincount(lab))[::-1])
    if best is None or s > best[0]:
        best = (s, K, lab)
_, K, lab = best
res = pd.DataFrame({"own_rhythm": own.astype(int), "rhythm_type": -1, "rep_total": rep["total"], "rep_cafe": rep["cafe"],
                    "amp_total": amp["total"], "amp_cafe": amp["cafe"]}, index=prof.index)
res.loc[own.values, "rhythm_type"] = lab
res = res.join(mo[["name", "region_name"]])
res.to_csv(out / "mo_rhythm.csv")

rows, profs = [], []
for k in range(K):
    m = res.rhythm_type == k
    mean_prof = prof[m.values].mean()
    pk = {c: int(mean_prof[c].idxmax()) for c in cats}
    rows.append({"rhythm_type": k, "n": int(m.sum()), "peak_month_total": pk["total"], "peak_month_cafe": pk["cafe"],
                 "amp_total": float(mean_prof["total"].max() - mean_prof["total"].min()),
                 "top_regions": "; ".join(f"{r} ({n})" for r, n in res[m].region_name.value_counts().head(4).items()),
                 "examples": ", ".join(res[m].sort_values("rep_total", ascending=False).name.head(6))})
    profs.append(mean_prof.rename(k))
types = pd.DataFrame(rows)
types.to_csv(out / "types.csv", index=False)
pd.concat(profs, axis=1).T.to_csv(out / "profiles.csv")
print(types.to_string())
for k in range(K):
    print(k, "total:", " ".join(f"{v:+.2f}" for v in profs[k]["total"].values), "| cafe:",
          " ".join(f"{v:+.2f}" for v in profs[k]["cafe"].values))
