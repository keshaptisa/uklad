"""Шаг 6б. Проверки устойчивости выводов (python scripts/s21_robustness.py; около 10–15 минут на CPU).

1. Вне выборки: типы строятся только по 2023 году (уровень трат и сеть DTW по 12 месяцам), 2024 год размечается
   ближайшим центром 2023 года в пространстве признаков; сравнение с независимой кластеризацией 2024 года и с основной.
2. Число соседей k в графе: k = 10, 15, 25 — насколько меняется типология (ARI с основной) и её качество.
3. Рейтинг методов при K − 1 и K + 1 (без CANUS — он один идёт ~5 минут на запуск): не держится ли первое место
   основного метода только на выбранном K.
4. Различие лидеров: на 20 подвыборках по 80% МО — доля подвыборок, где основной метод лучше k-means по каждому индексу.

Выход: outputs/robustness/{out_of_sample.json, k_sensitivity.csv, ranking_by_K.csv, leaders.csv}
"""
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ARI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uklad import load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import attributes as F  # noqa: E402
from uklad import network as G  # noqa: E402
from uklad.matrix import load  # noqa: E402
from uklad.quality import icvi, icvi_z  # noqa: E402
from uklad.aggregate import threshold_aggregation  # noqa: E402

cfg = load_config()
tc, er = cfg["typology"], cfg["edges"]
K, seed, k0 = tc["K"], cfg["seed"], er["k"]
out = ROOT / cfg["paths"]["outputs"] / "robustness"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
ids, Y, A = np.asarray(d.ids), d.Y.values, d.A
main = pd.read_csv(ROOT / cfg["paths"]["outputs"] / "method_comparison" / "labels.csv", index_col=0)
main_name = "KEFRiN-c (признаки+сеть)" if tc["metric"] == "cosine" else "KEFRiN-e (признаки+сеть)"
y_main = main.loc[ids, main_name].values


def kef(Y, A, K, s=seed):
    return C.kefrin(Y, C.modularity_rows(A), K, metric=tc["metric"], seed=s, n_init=10)


# ряды для DTW — так же, как в s03_edges.py
spend = pd.read_parquet(ROOT / cfg["paths"]["processed"] / "spend.parquet")
mf = F.monthly_features(spend)
cons_cols = ["level"] + [f"clr_{p}" for p in F.PARTS] + ["engel"]
ser = mf[cons_cols]
ser = (ser - ser.mean()) / ser.std()
T = np.stack([ser.xs(i, level=0).values for i in ids])
t0 = time.time()

# ---------- 1. вне выборки ----------
lvl = mf["level"].unstack("month").loc[ids]
months = list(lvl.columns)
attrs = tc["attributes"]
base = d.Y.copy()


def Y_year(cols):
    """Признаки с уровнем трат за выбранные месяцы; остальные (Росстат) неизменны. Стандартизация — по 2023 году."""
    Yy = base.copy()
    raw = lvl[cols].mean(axis=1)
    ref = lvl[months[:12]].mean(axis=1)
    Yy["level"] = (raw - ref.mean()) / ref.std()
    return Yy[attrs].values


Y23, Y24 = Y_year(months[:12]), Y_year(months[12:])
print("DTW 2023 и 2024…", flush=True)
A23 = G.knn_graph(-G.dtw_dist(T[:, :12], window=er["dtw_window"]), k0)
A24 = G.knn_graph(-G.dtw_dist(T[:, 12:], window=er["dtw_window"]), k0)
y23, y24 = kef(Y23, A23, K), kef(Y24, A24, K)
cent = np.stack([Y23[y23 == c].mean(0) for c in range(K)])
nrm = lambda X: X / np.linalg.norm(X, axis=1, keepdims=True)
y24_pred = (nrm(Y24) @ nrm(cent).T).argmax(1) if tc["metric"] == "cosine" else ((Y24[:, None] - cent[None]) ** 2).sum(2).argmin(1)
oos = {"ari_2023_vs_main": ARI(y23, y_main), "ari_2024_vs_main": ARI(y24, y_main),
       "ari_2024pred_vs_2024fit": ARI(y24_pred, y24), "ari_2024pred_vs_main": ARI(y24_pred, y_main),
       "same_type_share_2023_to_2024pred": float((y24_pred == y23).mean())}
(out / "out_of_sample.json").write_text(json.dumps(oos, ensure_ascii=False, indent=1), encoding="utf-8")
print("вне выборки:", {k: round(v, 3) for k, v in oos.items()}, f"{time.time() - t0:.0f} с", flush=True)

# ---------- 2. число соседей k ----------
D = G.dtw_dist(T, window=er["dtw_window"])
rows = []
for k in (10, 15, 25):
    Ak = G.knn_graph(-D, k)
    yk = kef(Y, Ak, K)
    m = icvi(Y, Ak, yk)
    rows.append({"k": k, "ARI с основной": ARI(yk, y_main), "SW": m["SW"], "AVI": m["AVI"], "MQ": m["MQ"]})
KS = pd.DataFrame(rows)
KS.to_csv(out / "k_sensitivity.csv", index=False)
print(KS.round(3).to_string(index=False), f"{time.time() - t0:.0f} с", flush=True)

# ---------- 3. рейтинг при K ± 1 ----------
METHODS = {
    "k-means (признаки)": lambda Y, A, K, s: C.kmeans(Y, K, seed=s),
    "Ward (признаки)": lambda Y, A, K, s: C.ward(Y, K),
    "GMM (признаки)": lambda Y, A, K, s: C.gmm(Y, K, seed=s),
    "спектральная (сеть)": lambda Y, A, K, s: C.spectral(A, K, seed=s),
    "Leiden (сеть)": lambda Y, A, K, s: C.leiden_k(A, K, seed=s),
    "KEFRiN-e (признаки+сеть)": lambda Y, A, K, s: C.kefrin(Y, C.modularity_rows(A), K, metric="euclidean", seed=s, n_init=10),
    "KEFRiN-c (признаки+сеть)": lambda Y, A, K, s: C.kefrin(Y, C.modularity_rows(A), K, metric="cosine", seed=s, n_init=10),
}
rng = np.random.default_rng(seed)
subs = [np.sort(rng.choice(len(Y), int(0.8 * len(Y)), replace=False)) for _ in range(10)]
crit = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]
res = []
for KK in (K - 1, K + 1):
    Z, boot = {}, {}
    for name, f in METHODS.items():
        y = f(Y, A, KK, seed)
        Z[name] = icvi_z(Y, A, y, n_perm=20, seed=seed)
        boot[name] = np.mean([ARI(y[s], f(Y[s], A[s][:, s], KK, seed + 1 + b)) for b, s in enumerate(subs)])
    Zd = pd.DataFrame(Z).T[crit]
    Zd["bootstrap_ARI"] = pd.Series(boot)
    r = threshold_aggregation(Zd)
    for name in r.index:
        res.append({"K": KK, "метод": name, "место (Алескеров)": int(r.loc[name, "rank_threshold"]), "место (Борда)": int(r.loc[name, "rank_borda"])})
    print(f"K={KK}:", r[["rank_threshold", "rank_borda"]].to_string(), f"{time.time() - t0:.0f} с", flush=True)
pd.DataFrame(res).to_csv(out / "ranking_by_K.csv", index=False)

# ---------- 4. различие лидеров на подвыборках ----------
better = {c: [] for c in crit}
for b, s in enumerate(subs + [np.sort(rng.choice(len(Y), int(0.8 * len(Y)), replace=False)) for _ in range(10)]):
    Ys, As = Y[s], A[s][:, s]
    mk = icvi(Ys, As, METHODS["k-means (признаки)"](Ys, As, K, seed + b))
    mm = icvi(Ys, As, METHODS[main_name](Ys, As, K, seed + b))
    for c in crit:
        lower_better = c in ("S_Dbw", "AVU")
        better[c].append((mm[c] < mk[c]) if lower_better else (mm[c] > mk[c]))
L = pd.DataFrame({"индекс": crit, "доля подвыборок, где основной метод лучше k-means": [float(np.mean(better[c])) for c in crit]})
L.to_csv(out / "leaders.csv", index=False)
print(L.round(2).to_string(index=False), f"{time.time() - t0:.0f} с")
