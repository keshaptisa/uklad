"""Шаг 4. Выбор числа типов K для основного метода (KEFRiN).

Для K из K_range: ICVI, бутстрап-устойчивость (ARI на 80%-подвыборках) и покластерная устойчивость Хеннига
(средний по бутстрапу максимальный Жаккар кластера; > 0,75 — устойчивый паттерн, > 0,85 — высокоустойчивый; Hennig 2007).

Выход: outputs/choose_k/summary.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ARI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad.matrix import load  # noqa: E402
from uklad.quality import icvi  # noqa: E402

cfg = load_config()
tcfg = cfg["typology"]
out = ROOT / cfg["paths"]["outputs"] / "choose_k"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
Y, A = d.Y.values, d.A
P = C.modularity_rows(A)
rng = np.random.default_rng(cfg["seed"])
subs = [np.sort(rng.choice(len(Y), int(0.8 * len(Y)), replace=False)) for _ in range(tcfg["bootstrap"])]


def hennig(y_full, y_sub, s):
    """Для каждого кластера полного разбиения — максимальный Жаккар с кластерами разбиения подвыборки."""
    ys = y_full[s]
    res = []
    for k in np.unique(y_full):
        a = set(np.where(ys == k)[0])
        best = max(len(a & set(np.where(y_sub == j)[0])) / max(len(a | set(np.where(y_sub == j)[0])), 1)
                   for j in np.unique(y_sub))
        res.append(best)
    return np.array(res)


rows = []
k0, k1 = tcfg["K_range"]
for K in range(k0, k1 + 1):
    y = C.kefrin(Y, P, K, seed=cfg["seed"], n_init=10, metric=cfg["typology"]["metric"])
    aris, jac = [], []
    for b, s in enumerate(subs):
        ys = C.kefrin(Y[s], C.modularity_rows(A[s][:, s]), K, seed=cfg["seed"] + 1 + b, n_init=5, metric=cfg["typology"]["metric"])
        aris.append(ARI(y[s], ys))
        jac.append(hennig(y, ys, s))
    jac = np.mean(jac, axis=0)
    r = {"K": K, **icvi(Y, A, y), "boot_ARI": np.mean(aris), "boot_ARI_sd": np.std(aris),
         "hennig_min": jac.min(), "hennig_mean": jac.mean(), "n_stable_085": int((jac > 0.85).sum()),
         "min_size": int(np.bincount(y).min())}
    rows.append(r)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)

pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)
