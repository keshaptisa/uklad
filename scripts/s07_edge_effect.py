"""Шаг 3б. Как правило ребра меняет итоговую типологию и что сеть добавляет к признакам.

1. KEFRiN с одними и теми же атрибутами на каждом из графов (cosine, rbf, corr, lagcorr, dtw, road, context):
   согласие с основной типологией (ARI), «региональность» типов (ARI с регионом), ICVI на своём графе.
2. Что делает сеть: МО, у которых тип KEFRiN ≠ тип k-means по тем же признакам. Для них сравниваем долю соседей
   по графу потребления, попавших в тот же тип, при двух разбиениях: если сеть «тянет» МО к тем, на кого он похож по тратам,
   эта доля при KEFRiN выше.

Выход: outputs/edge_effect/{by_rule.csv, network_moves.csv, summary.json}
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.metrics import adjusted_rand_score as ARI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad.matrix import load  # noqa: E402
from uklad.quality import icvi  # noqa: E402

cfg = load_config()
K, seed = cfg["typology"]["K"], cfg["seed"]
out = ROOT / cfg["paths"]["outputs"] / "edge_effect"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
Y = d.Y.values
Pdir = ROOT / cfg["paths"]["processed"] / "graphs"
region = pd.factorize(d.mo.region_name)[0]

y_main = C.kefrin(Y, C.modularity_rows(d.A), K, seed=seed, n_init=10, metric=cfg["typology"]["metric"])
y_km = C.kmeans(Y, K, seed=seed)
rows = []
for f in sorted(Pdir.glob("static_*.npz")):
    rule = f.stem.replace("static_", "")
    A = sp.load_npz(f).tocsr()
    y = C.kefrin(Y, C.modularity_rows(A), K, seed=seed, n_init=10, metric=cfg["typology"]["metric"])
    m = icvi(Y, A, y)
    rows.append({"rule": rule, "ARI_with_main": ARI(y_main, y), "ARI_with_kmeans": ARI(y_km, y),
                 "ARI_with_region": ARI(region, y), **{k: m[k] for k in ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]}})
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
rows.append({"rule": "без сети (k-means)", "ARI_with_main": ARI(y_main, y_km), "ARI_with_kmeans": 1.0,
             "ARI_with_region": ARI(region, y_km), **{k: v for k, v in icvi(Y, d.A, y_km).items()
                                                     if k in ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]}})
pd.DataFrame(rows).set_index("rule").to_csv(out / "by_rule.csv")

# что добавляет сеть: МО, которые KEFRiN относит не туда, куда k-means
yk = C.align_labels(y_main, y_km, K)
moved = np.where(yk != y_main)[0]
A = d.A.tocsr()


def same_type_share(i, y):
    nb = A.indices[A.indptr[i]:A.indptr[i + 1]]
    w = A.data[A.indptr[i]:A.indptr[i + 1]]
    return float((w * (y[nb] == y[i])).sum() / w.sum()) if len(nb) else np.nan


mv = pd.DataFrame({"territory_id": d.ids[moved], "name": d.mo.name.values[moved], "region": d.mo.region_name.values[moved],
                   "type_kmeans": yk[moved], "type_kefrin": y_main[moved],
                   "neighbors_same_type_kmeans": [same_type_share(i, yk) for i in moved],
                   "neighbors_same_type_kefrin": [same_type_share(i, y_main) for i in moved]})
mv.to_csv(out / "network_moves.csv", index=False)
summary = {"n_moved": int(len(moved)), "share_moved": float(len(moved) / len(Y)),
           "neighbors_same_type_kmeans_mean": float(mv.neighbors_same_type_kmeans.mean()),
           "neighbors_same_type_kefrin_mean": float(mv.neighbors_same_type_kefrin.mean()),
           "all_mo_same_type_kmeans": float(np.nanmean([same_type_share(i, yk) for i in range(len(Y))])),
           "all_mo_same_type_kefrin": float(np.nanmean([same_type_share(i, y_main) for i in range(len(Y))]))}
json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(summary)
