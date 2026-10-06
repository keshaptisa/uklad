"""Шаг 5в. Проверка способов отслеживания типов на синтетике с известной истиной.

Генератор откалиброван по реальным данным: центры типов c_k и устойчивые отклонения МО u_i = Y_i − c_{y_i} берутся
из основной типологии; помесячный шум ε_t ~ N(0, σ) с σ, равным реальному месячному разбросу уровня трат вокруг
среднего МО (только по признаку уровня, как в реальных данных: экономическая база помесячно не меняется),
и вариант с шумом ×2 по всем признакам. В месяце 12 доля migrate МО переходит в ближайший другой тип: Y_i = c_new + u_i.
Сеть месяца — kNN по сходству синтетических признаков (как помесячная сеть в реальности строится по тратам месяца).

Метрики: доля мигрантов, которых метод отнёс к новому типу через 0/2/4 месяца после события; доля ложных смен у
остальных МО за 24 месяца; NMI с истиной.

Выход: outputs/synthetic/summary.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score as NMI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import network as G  # noqa: E402
from uklad import tracking as TM  # noqa: E402
from uklad.matrix import load  # noqa: E402

cfg = load_config()
sc = cfg["synthetic"]
K, seed = cfg["typology"]["K"], cfg["seed"]
out = ROOT / cfg["paths"]["outputs"] / "synthetic"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
rng = np.random.default_rng(seed)
idx = np.sort(rng.choice(len(d.ids), sc["n_nodes"], replace=False))
Y = d.Y.values[idx]
y_true0 = C.kefrin(d.Y.values, C.modularity_rows(d.A), K, seed=seed, n_init=10, metric=cfg["typology"]["metric"])[idx]
cent = np.stack([Y[y_true0 == k].mean(0) for k in range(K)])
U = Y - cent[y_true0]
lvl_col = list(d.Y.columns).index("level")
lv = d.monthly["level"].unstack()
sigma_level = float((lv.sub(lv.mean(1), axis=0)).stack().std() / d.monthly["level"].std())  # в единицах стандартизованного признака
print(f"калиброванный σ уровня трат = {sigma_level:.3f}")
T, t0 = 24, 12


def simulate(noise_all, rs):
    yt = np.repeat(y_true0[None, :], T, 0)
    mig = rs.choice(len(Y), int(sc["migrate"] * len(Y)), replace=False)
    dist = ((cent[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(dist, np.inf)
    new = dist[y_true0[mig]].argmin(1)
    yt[t0:, mig] = new
    Ys, As = [], []
    for t in range(T):
        base = cent[yt[t]] + U
        eps = np.zeros_like(base)
        if noise_all:
            eps = rs.normal(0, noise_all, base.shape)
        eps[:, lvl_col] += rs.normal(0, sigma_level, len(base))
        Yt = base + eps
        Ys.append(Yt)
        As.append(G.knn_graph(G.cosine_sim(Yt), cfg["edges"]["k"]))
    return Ys, As, yt, mig


rows = []
for scen, noise_all in [("калиброванный", 0.0), ("шум ×2 по всем признакам", 2 * sigma_level)]:
    for rep in range(sc["reps"]):
        rs = np.random.default_rng(seed + 100 + rep)
        Ys, As, yt, mig = simulate(noise_all, rs)
        rho, xi = C.kefrin_weights(Ys[0], C.modularity_rows(As[0]))
        variants = {"независимо": TM.independent_kefrin(Ys, As, K, y_true0, rho, xi, seed, metric=cfg["typology"]["metric"])}
        for a in cfg["dynamics"]["alphas"]:
            variants[f"эволюционный, α={a}"] = TM.evolutionary_kefrin(Ys, As, K, a, y_true0, rho, xi, seed, metric=cfg["typology"]["metric"])
        non = np.setdiff1d(np.arange(len(Y)), mig)
        for name, L in variants.items():
            # метки уже согласованы с y_true0 (старт и венгерское выравнивание)
            r = {"сценарий": scen, "повтор": rep, "вариант": name,
                 "NMI": float(np.mean([NMI(yt[t], L[t]) for t in range(T)])),
                 "ложные смены (не мигранты)": float((L[1:, non] != L[:-1, non]).sum() / len(non)),
                 "переходов на МО у мигрантов": float((L[1:, mig] != L[:-1, mig]).sum() / len(mig))}
            for lag in (0, 2, 4):
                r[f"мигранты найдены через {lag} мес."] = float((L[t0 + lag, mig] == yt[t0 + lag, mig]).mean())
            rows.append(r)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)

res = pd.DataFrame(rows)
summ = res.drop(columns="повтор").groupby(["сценарий", "вариант"], sort=False).mean()
summ.to_csv(out / "summary.csv")
print(summ.round(3).to_string())
