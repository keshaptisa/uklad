"""Шаг 7в. Раскладка сети МО для лендинга и статистика рёбер.

Узлы — 2 016 МО, рёбра — основное правило (DTW-kNN, configs/pipeline.yaml: typology.graph).
Раскладка — силовая (Фрюхтерман — Рейнгольд, networkx) из начального положения по спектральному вложению:
близкие по тратам МО оказываются рядом независимо от географии.
Для браузера оставляем у каждого МО 3 самых сильных ребра (остальные не видны при 2 016 точках).

Выход: outputs/network/{layout.csv, edges.csv, summary.json}
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uklad import load_config  # noqa: E402
from uklad.matrix import load  # noqa: E402

cfg = load_config()
d = load(cfg)
A = d.A.tocsr()
A = A.maximum(A.T)
ids = np.asarray(d.ids)
out = ROOT / cfg["paths"]["outputs"] / "network"
out.mkdir(parents=True, exist_ok=True)

G = nx.from_scipy_sparse_array(A)
init = nx.spectral_layout(G, dim=2)
pos = nx.spring_layout(G, pos=init, k=1.4 / np.sqrt(G.number_of_nodes()), iterations=300, seed=cfg["seed"], weight="weight")
P = np.array([pos[i] for i in range(len(ids))])
P = (P - P.min(0)) / (P.max(0) - P.min(0))
pd.DataFrame({"territory_id": ids, "x": P[:, 0].round(4), "y": P[:, 1].round(4)}).to_csv(out / "layout.csv", index=False)

# 3 самых сильных ребра у каждого МО
rows = set()
for i in range(A.shape[0]):
    s, e = A.indptr[i], A.indptr[i + 1]
    nb, w = A.indices[s:e], A.data[s:e]
    for j in nb[np.argsort(-w)[:3]]:
        rows.add((min(i, j), max(i, j)))
E = pd.DataFrame(sorted(rows), columns=["a", "b"])
E["a_id"], E["b_id"] = ids[E.a], ids[E.b]
E[["a_id", "b_id"]].to_csv(out / "edges.csv", index=False)

# статистика всех рёбер графа
T = pd.read_csv(ROOT / cfg["paths"]["outputs"] / "interpret" / "mo_types.csv").set_index("territory_id").loc[ids]
mo = pd.read_parquet(ROOT / cfg["paths"]["processed"] / "mo.parquet").loc[ids]
C = A.tocoo()
m = C.row < C.col
r, c = C.row[m], C.col[m]
same_type = (T.type.values[r] == T.type.values[c]).mean()
same_reg = (mo.region_code.values[r] == mo.region_code.values[c]).mean()
lat, lon = np.radians(mo.lat.values), np.radians(mo.lon.values)
dist = 6371 * 2 * np.arcsin(np.sqrt(np.sin((lat[c] - lat[r]) / 2) ** 2 + np.cos(lat[r]) * np.cos(lat[c]) * np.sin((lon[c] - lon[r]) / 2) ** 2))
summ = {"nodes": int(len(ids)), "edges": int(m.sum()), "edges_shown": int(len(E)),
        "same_type": float(same_type), "same_region": float(same_reg),
        "dist_median_km": float(np.nanmedian(dist)), "dist_over_1000_share": float(np.nanmean(dist > 1000))}
(out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
print(summ)
