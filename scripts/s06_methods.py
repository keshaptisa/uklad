"""Шаг 3. Сравнение методов кластеризации на основной атрибутированной сети при общем K.

Методы: только признаки (k-means, Ward, GMM), только сеть (спектральная, Leiden, Louvain), признаки + сеть
(Ward с ограничением связности; KEFRiN евклидов и косинусный — Shalileh & Mirkin 2022; CANUS — Shalileh 2025),
глубокие графовые (GAE + k-means — Kipf & Welling 2016; DAEGC — Wang et al. 2019; DMoN — Tsitsulin et al. 2023).
Для каждого: ICVI (сырые и z против перестановки меток), бутстрап-устойчивость, время.
Итог — рейтинг пороговым агрегированием Алескерова и Борда.

Выход: outputs/method_comparison/{icvi_raw.csv, icvi_z.csv, ranking.csv, ari_between.csv, labels.csv}
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ARI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import gnn  # noqa: E402
from uklad.matrix import load  # noqa: E402
from uklad.quality import icvi, icvi_z  # noqa: E402
from uklad.aggregate import threshold_aggregation  # noqa: E402

cfg = load_config()
tcfg = cfg["typology"]
K, seed = tcfg["K"], cfg["seed"]
out = ROOT / cfg["paths"]["outputs"] / "method_comparison"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
Y, A = d.Y.values, d.A


def kef(metric):
    return lambda Y, A, K, s: C.kefrin(Y, C.modularity_rows(A), K, metric=metric, seed=s, n_init=10)


METHODS = {
    "k-means (признаки)": lambda Y, A, K, s: C.kmeans(Y, K, seed=s),
    "Ward (признаки)": lambda Y, A, K, s: C.ward(Y, K),
    "GMM (признаки)": lambda Y, A, K, s: C.gmm(Y, K, seed=s),
    "спектральная (сеть)": lambda Y, A, K, s: C.spectral(A, K, seed=s),
    "Leiden (сеть)": lambda Y, A, K, s: C.leiden_k(A, K, seed=s),
    "Louvain (сеть)": lambda Y, A, K, s: C.louvain_k(A, K, seed=s),
    "Ward со связностью (признаки+сеть)": lambda Y, A, K, s: C.ward_net(Y, A, K),
    "KEFRiN-e (признаки+сеть)": kef("euclidean"),
    "KEFRiN-c (признаки+сеть)": kef("cosine"),
    "CANUS (признаки+сеть)": lambda Y, A, K, s: C.canus(Y, A, K, seed=s),
    "GAE + k-means (GNN)": lambda Y, A, K, s: gnn.gae_kmeans(Y, A, K, seed=s),
    "DAEGC (GNN)": lambda Y, A, K, s: gnn.daegc(Y, A, K, seed=s),
    "DMoN (GNN)": lambda Y, A, K, s: gnn.dmon(Y, A, K, seed=s),
}

# Набор, по которому выбирался основной метод (зафиксирован до сравнения); остальные — внешний контроль.
SELECTION = ["k-means (признаки)", "Ward (признаки)", "GMM (признаки)", "спектральная (сеть)", "Leiden (сеть)",
             "KEFRiN-e (признаки+сеть)", "KEFRiN-c (признаки+сеть)", "CANUS (признаки+сеть)"]

rng = np.random.default_rng(seed)
B = tcfg["bootstrap"]
subs = [np.sort(rng.choice(len(Y), int(0.8 * len(Y)), replace=False)) for _ in range(B)]

labels, raw, zs, meta = {}, {}, {}, {}
for name, f in METHODS.items():
    t = time.time()
    try:
        y = f(Y, A, K, seed)
    except ImportError as e:
        print("пропуск", name, e)
        continue
    dt = time.time() - t
    labels[name] = y
    raw[name] = icvi(Y, A, y)
    zs[name] = icvi_z(Y, A, y, n_perm=tcfg["n_perm"], seed=seed)
    nb = B if dt < 20 else max(3, B // 4)
    boot = [ARI(y[s], f(Y[s], A[s][:, s], K, seed + 1 + b)) for b, s in enumerate(subs[:nb])]
    meta[name] = {"K_found": len(np.unique(y)), "min_size": int(np.bincount(y).min()), "seconds": round(dt, 1),
                  "bootstrap_ARI": float(np.mean(boot)), "bootstrap_ARI_sd": float(np.std(boot)), "n_boot": nb}
    print(f"{name:<28} {meta[name]} " + " ".join(f"{k}={v:.3f}" for k, v in raw[name].items()), flush=True)

R = pd.DataFrame(raw).T.join(pd.DataFrame(meta).T)
Z = pd.DataFrame(zs).T
R.to_csv(out / "icvi_raw.csv")
Z.to_csv(out / "icvi_z.csv")
crit = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]
crit_plus = Z[crit].join(R[["bootstrap_ARI"]])
# Рейтинг выбора — по набору SELECTION (правило выбора задано до добавления контрольных методов).
# Контроль (графовые нейросети, Louvain, Ward со связностью) — в общем рейтинге всех методов, ranking_all.csv.
# Места относительны (трети по каждому критерию), поэтому новые участники сдвигают пороги.
base = crit_plus.index.isin(SELECTION)
rank = threshold_aggregation(crit_plus[base])
rank.to_csv(out / "ranking.csv")
threshold_aggregation(crit_plus).to_csv(out / "ranking_all.csv")
print("\nРейтинг (6 ICVI в z-оценках + бутстрап-устойчивость):")
print(rank.to_string())

names = list(labels)
ari = pd.DataFrame([[ARI(labels[a], labels[b]) for b in names] for a in names], index=names, columns=names)
ari.to_csv(out / "ari_between.csv")
print("\nСогласие методов (ARI):\n", ari.round(2).to_string())
pd.DataFrame(labels, index=d.ids).to_csv(out / "labels.csv")
