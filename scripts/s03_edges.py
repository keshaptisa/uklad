"""Шаг 2. Сравнение правил ребра: какую «экономическую близость» измеряет каждое и как оно меняет сеть.

Выход: outputs/edges/{summary.csv, jaccard.csv}, data/processed/graphs/*.npz
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import attributes as F  # noqa: E402
from uklad import network as G  # noqa: E402
from uklad.partition import leiden  # noqa: E402
from uklad.quality import graph_icvi  # noqa: E402

cfg = load_config()
P = ROOT / cfg["paths"]["processed"]
out = ROOT / cfg["paths"]["outputs"] / "edges"
out.mkdir(parents=True, exist_ok=True)
(P / "graphs").mkdir(exist_ok=True)
er = cfg["edges"]
k = er["k"]

spend = pd.read_parquet(P / "spend.parquet")
mo = pd.read_parquet(P / "mo.parquet")
mf = F.monthly_features(spend)
ids = mf.index.get_level_values(0).unique().values
mo = mo.loc[ids]
ctx = F.context(mo)

# статический профиль потребления: среднее по 24 месяцам
cons_cols = ["level"] + [f"clr_{p}" for p in F.PARTS] + ["engel"]
static = F.standardize(mf[cons_cols].groupby(level=0).mean()).loc[ids]
# ряды: каналы стандартизованы по всей панели
ser = mf[cons_cols].copy()
ser = (ser - ser.mean()) / ser.std()
T = np.stack([ser.xs(i, level=0).values for i in ids])            # N × 24 × 8
T_dev = T - T.mean(axis=1, keepdims=True)                           # без собственного среднего МО: только движение

sims = {}
sims["cosine"] = G.cosine_sim(static.values)
sims["rbf"] = G.rbf_sim(static.values)
sims["corr"] = G.corr_sim(T_dev.reshape(len(ids), -1))
lc, lag = G.lagcorr_sim(T_dev[:, :, 0], max_lag=er["max_lag"])
sims["lagcorr"] = lc
print("DTW…", flush=True)
D = G.dtw_dist(T, window=er["dtw_window"])
sims["dtw"] = -D
conn = pd.read_parquet(ROOT / cfg["paths"]["raw"] / "hackathonlicence" / "connection.parquet")
Dr = G.road_distance(ids, conn, "highway")
sims["road"] = G.road_sim(Dr, er["road_d0"])
sims["context"] = G.cosine_sim(F.standardize(ctx).values)
# слияние трёх взглядов: «как тратят» (DTW), «чем живут» (экономическая база), «где» (дороги)
print("SNF…", flush=True)
Dctx = 1 - sims["context"]
Droad = np.where(np.isfinite(Dr), Dr, np.nanmax(Dr[np.isfinite(Dr)]) * 2)
sims["snf"] = G.snf([D / D.mean(), Dctx / Dctx.mean(), Droad / Droad.mean()], K=er.get("snf_k", 20))

graphs = {}
for name, S in sims.items():
    graphs[name] = G.knn_graph(S, k, mutual=False)
    sp.save_npz(P / "graphs" / f"static_{name}.npz", graphs[name])

region = mo["region_name"].values
attrs = {"log_wage": ctx["log_wage"].values, "urban_share": ctx["urban_share"].values,
         "emp_mining": ctx["emp_mining"].values, "emp_agro": ctx["emp_agro"].values,
         "level": static["level"].values, "clr_market": static["clr_market"].values}

rows = []
for name, A in graphs.items():
    Au = sp.triu(A, 1).tocoo()
    i, j = Au.row, Au.col
    import scipy.sparse.csgraph as cg
    ncomp, comp = cg.connected_components(A, directed=False)
    r = {"rule": name, "edges": len(i), "mean_degree": 2 * len(i) / len(ids),
         "giant_share": np.bincount(comp).max() / len(ids),
         "within_region": float((region[i] == region[j]).mean())}
    # гомофилия: корреляция признака на концах рёбер
    for a, v in attrs.items():
        r[f"homoph_{a}"] = float(np.corrcoef(np.r_[v[i], v[j]], np.r_[v[j], v[i]])[0, 1])
    y = leiden(A, 1.0, seed=cfg["seed"])
    r["leiden_communities"] = int((np.bincount(y) >= 0.01 * len(ids)).sum())
    r["leiden_Q"] = graph_icvi(A, y)["MQ"]
    rows.append(r)
    print(name, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in r.items()}, flush=True)

summ = pd.DataFrame(rows).set_index("rule")
summ.to_csv(out / "summary.csv")
names = list(graphs)
jac = pd.DataFrame([[G.edge_jaccard(graphs[a], graphs[b]) for b in names] for a in names], index=names, columns=names)
jac.to_csv(out / "jaccard.csv")
print(jac.round(2).to_string())

# лаги: у скольких пар соседей по lagcorr лучший сдвиг ≠ 0
A = graphs["lagcorr"].tocoo()
nz = lag[A.row, A.col]
print("доля рёбер lagcorr с ненулевым лагом:", round(float((nz != 0).mean()), 3))
