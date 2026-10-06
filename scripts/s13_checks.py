"""Шаг 7б. Дополнительные проверки поверх готовых результатов (без пересчёта кластеризации).

1. Устойчивость рейтинга методов: 8 вариантов (Алескеров / Борда × с AVU / без × с бутстрапом / без).
2. «Отпечатки типов»: на сколько стандартных отклонений медиана типа отличается от медианы по России.
3. Расхождение типов во времени: траты на жителя каждого типа относительно медианы страны по месяцам,
   σ-сходимость (разброс логарифма трат между МО) и доля разброса, объясняемая типом (η²).

Выход: outputs/method_comparison/ranking_variants.csv, outputs/interpret/{fingerprint.csv, divergence.csv, divergence_summary.json}
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uklad.aggregate import threshold_aggregation  # noqa: E402

# ---------- 1. варианты рейтинга ----------
M = ROOT / "outputs" / "method_comparison"
Z = pd.read_csv(M / "icvi_z.csv", index_col=0)
R = pd.read_csv(M / "icvi_raw.csv", index_col=0)
base = Z.index.isin(pd.read_csv(M / "ranking.csv", index_col=0).index)  # только набор выбора, контроль — отдельно
Z, R = Z[base], R[base]
rows = {}
for avu in (True, False):
    for boot in (True, False):
        crit = ["SW", "CH", "S_Dbw", "AVI"] + (["AVU"] if avu else []) + ["MQ"]
        X = Z[crit].join(R[["bootstrap_ARI"]]) if boot else Z[crit]
        r = threshold_aggregation(X)
        tag = ("с AVU" if avu else "без AVU") + (", с бутстрапом" if boot else ", без бутстрапа")
        rows[f"Алескеров: {tag}"] = r["rank_threshold"]
        rows[f"Борда: {tag}"] = r["rank_borda"]
V = pd.DataFrame(rows)
V["лучшее место"], V["худшее место"] = V.min(1), V.max(1)
V["первых мест"] = (V.iloc[:, :8] == 1).sum(1)
V = V.sort_values(["худшее место", "лучшее место"])
V.to_csv(M / "ranking_variants.csv")
print("Рейтинг в 8 вариантах:\n", V[["лучшее место", "худшее место", "первых мест"]].to_string())

# ---------- 2. отпечатки типов ----------
I = ROOT / "outputs" / "interpret"
T = pd.read_csv(I / "mo_types.csv")
feats = {"spend": "траты на жителя", "wage": "зарплата", "population": "население", "urban_share": "доля горожан",
         "market_access": "доступность рынков", "share_food": "доля продовольствия", "share_cafe": "доля общепита",
         "share_market": "доля маркетплейсов", "share_health": "доля здоровья", "share_transport": "доля транспорта",
         "emp_agro": "занятость: сельское хоз.", "emp_mining": "занятость: добыча", "emp_industry": "занятость: промышленность",
         "emp_transport": "занятость: транспорт", "emp_market_services": "занятость: рыночные услуги", "emp_public": "занятость: бюджетный сектор"}
feats = {k: v for k, v in feats.items() if k in T}
X = T[list(feats)].copy()
for c in ("spend", "wage", "population", "market_access"):
    if c in X:
        X[c] = np.log(X[c].clip(lower=1e-9))
# (медиана типа − медиана страны) / стандартное отклонение по стране; IQR не годится — у долей добычи он почти нулевой
F = (X.groupby(T["type_name"]).median() - X.median()) / X.std()
F.columns = [feats[c] for c in F.columns]
F.round(3).to_csv(I / "fingerprint.csv")
print("\nОтпечатки (в σ страны):\n", F.round(2).to_string())

# ---------- 3. расхождение типов во времени ----------
S = pd.read_parquet(ROOT / "data" / "processed" / "spend.parquet")
S = S[S.category == "total"].pivot(index="territory_id", columns="month", values="value")
S = S.loc[S.index.intersection(T["territory_id"])]
typ = T.set_index("territory_id").loc[S.index, "type_name"]
L = np.log(S.clip(lower=1))
rel = L.sub(L.median(0), axis=1)                                   # лог-отклонение от медианы страны в месяце
by_type = (np.exp(rel.groupby(typ).median()) - 1) * 100            # % к медиане страны
sigma = L.std(0)
eta2 = rel.apply(lambda col: col.groupby(typ).apply(lambda g: len(g) * (g.mean() - col.mean()) ** 2).sum() / ((col - col.mean()) ** 2).sum())
D = by_type.T.round(2)
D["σ лог-трат между МО"], D["η² типа"] = sigma.round(4), eta2.round(4)
D.index.name = "month"
D.to_csv(I / "divergence.csv")
# по годам: среднее 2023 против 2024, чтобы сезон не мешал
y = {yr: by_type.loc[:, [m for m in by_type.columns if m.startswith(yr)]].mean(1) for yr in ("2023", "2024")}
summ = {"gap_pct_2023": y["2023"].round(2).to_dict(), "gap_pct_2024": y["2024"].round(2).to_dict(),
        "sigma_2023": float(sigma[[m for m in sigma.index if m.startswith("2023")]].mean()),
        "sigma_2024": float(sigma[[m for m in sigma.index if m.startswith("2024")]].mean()),
        "eta2_2023": float(eta2[[m for m in eta2.index if m.startswith("2023")]].mean()),
        "eta2_2024": float(eta2[[m for m in eta2.index if m.startswith("2024")]].mean()),
        "top_type": y["2024"].idxmax(), "bottom_type": y["2024"].idxmin()}
summ["spread_2023"] = float(y["2023"].max() - y["2023"].min())
summ["spread_2024"] = float(y["2024"].max() - y["2024"].min())
# бутстрап по МО внутри типов: значимо ли изменились разрыв между полюсами и σ за год
yr = {yr: [m for m in rel.columns if m.startswith(yr)] for yr in ("2023", "2024")}
rng = np.random.default_rng(42)
d_spread, d_sigma = [], []
grp = {t: np.where(typ.values == t)[0] for t in typ.unique()}
for _ in range(1000):
    idx = np.concatenate([rng.choice(ix, len(ix)) for ix in grp.values()])
    rb, tb, Lb = rel.iloc[idx], typ.iloc[idx].values, L.iloc[idx]
    gm = {yy: (np.exp(rb[cols].groupby(tb).median()) - 1).mean(axis=1) * 100 for yy, cols in yr.items()}
    d_spread.append((gm["2024"].max() - gm["2024"].min()) - (gm["2023"].max() - gm["2023"].min()))
    sb = Lb.std(axis=0)
    d_sigma.append(sb[yr["2024"]].mean() - sb[yr["2023"]].mean())
summ["spread_change_ci95"] = [float(np.quantile(d_spread, .025)), float(np.quantile(d_spread, .975))]
summ["sigma_change_ci95"] = [float(np.quantile(d_sigma, .025)), float(np.quantile(d_sigma, .975))]
print(f"изменение разрыва: {summ['spread_2024'] - summ['spread_2023']:+.1f} п. п., 95% ДИ {summ['spread_change_ci95'][0]:+.1f}…{summ['spread_change_ci95'][1]:+.1f}; "
      f"изменение σ: 95% ДИ {summ['sigma_change_ci95'][0]:+.4f}…{summ['sigma_change_ci95'][1]:+.4f}")
(I / "divergence_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nТраты типа к медиане страны, % (2023 → 2024):")
for k in y["2023"].index:
    print(f"  {k:<42} {y['2023'][k]:+6.1f} → {y['2024'][k]:+6.1f}")
print(f"σ: {summ['sigma_2023']:.3f} → {summ['sigma_2024']:.3f};  η² типа: {summ['eta2_2023']:.3f} → {summ['eta2_2024']:.3f}")

# ---------- 4. что стоит за каждым ритмом: категории трат в пиковый месяц ----------
# Проверка трактовок: завоз поднимает продовольствие, сезонный приток людей — общепит и здоровье,
# сезонная добыча связана с долей занятых в добыче. Та же методика, что в линзе ритма (features.rhythm):
# лог-отклонение от медианы страны в месяце, минус собственный тренд МО, среднее двух лет; затем среднее по МО ритма.
# Поэтому «все траты» и «общепит» здесь совпадают со средним профилем ритма (outputs/rhythm/profiles.csv).
import yaml  # noqa: E402
from uklad import attributes as FE  # noqa: E402

RH = ROOT / "outputs" / "rhythm"
rt = pd.read_csv(RH / "types.csv").set_index("rhythm_type")
mr = pd.read_csv(RH / "mo_rhythm.csv").set_index("territory_id")
names = yaml.safe_load(open(ROOT / "configs" / "typology.yaml", encoding="utf-8"))["rhythm_names"]
cats = {"total": "все траты", "food": "продовольствие", "cafe": "общепит", "health": "здоровье", "market": "маркетплейсы", "transport": "транспорт"}
SP = pd.read_parquet(ROOT / "data" / "processed" / "spend.parquet")
prof, _ = FE.rhythm(SP, tuple(cats))
emp = T.set_index("territory_id")[["emp_mining"]]
rows = []
for k, r in rt.iterrows():
    ids = mr.index[mr["rhythm_type"] == k].intersection(prof.index)
    pm = int(r.peak_month_total)
    row = {"ритм": names.get(int(k), k), "МО": int(r.n), "пиковый месяц": pm}
    for c, ru in cats.items():
        row[ru + ", %"] = round(float(prof.loc[ids, (c, pm)].mean() * 100), 1)
    row["добыча > 5% занятых, доля МО"] = round(float((emp.reindex(ids)["emp_mining"] > 5).mean()), 2)
    row["то же по стране"] = round(float((emp["emp_mining"] > 5).mean()), 2)
    rows.append(row)
RC = pd.DataFrame(rows)
RC.to_csv(RH / "peak_by_category.csv", index=False)
print("\nРитмы: средний профиль в пиковый месяц по категориям (100 × лог-отклонение):\n", RC.to_string(index=False))

# ---------- BasicMQ (Mancoridis 1998) и устойчивость рейтинга к выбору трактовки MQ ----------
from uklad.matrix import load  # noqa: E402
from uklad.quality import graph_icvi  # noqa: E402

from uklad import load_config  # noqa: E402
cfg = load_config()
d = load(cfg)
L = pd.read_csv(M / "labels.csv", index_col=0)
rng = np.random.default_rng(cfg["seed"])
rows = {}
for m in L.columns:
    y = L[m].values
    v = graph_icvi(d.A, y, basic=True)["MQ_basic"]
    perm = [graph_icvi(d.A, rng.permutation(y), basic=True)["MQ_basic"] for _ in range(cfg["typology"]["n_perm"])]
    rows[m] = {"MQ_basic": v, "MQ_basic_z": (v - np.mean(perm)) / (np.std(perm) + 1e-12)}
B = pd.DataFrame(rows).T
B.to_csv(M / "mq_basic.csv")
sel = pd.read_csv(M / "ranking.csv", index_col=0).index
Zb = Z.copy()
Zb.loc[B.index.intersection(Zb.index), "MQ"] = B["MQ_basic_z"]
rb = threshold_aggregation(Zb.loc[sel, ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]].join(R.loc[sel, ["bootstrap_ARI"]]))
rb.to_csv(M / "ranking_mq_basic.csv")
print("\nBasicMQ:\n", B.round(4).to_string(), "\nРейтинг с BasicMQ вместо модулярности:\n", rb[["rank_threshold", "rank_borda"]].to_string())

# ---------- правило Коупленда и проверка на внешней сети (железные дороги) ----------
from uklad.aggregate import copeland  # noqa: E402
from uklad import network as G  # noqa: E402

crit7 = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]
cp_sel = copeland(Z.loc[sel, crit7].join(R.loc[sel, ["bootstrap_ARI"]]))
Za = pd.read_csv(M / "icvi_z.csv", index_col=0)
Ra = pd.read_csv(M / "icvi_raw.csv", index_col=0)
cp_all = copeland(Za[crit7].join(Ra[["bootstrap_ARI"]]))
pd.concat({"выбор (8 методов)": cp_sel, "все 13 методов": cp_all}, axis=1).to_csv(M / "ranking_copeland.csv")
print("\nКоупленд, набор выбора:\n", cp_sel.to_string(), "\nКоупленд, все методы:\n", cp_all.head(5).to_string())

# внешняя сеть: 15 ближайших по железной дороге — в построении типов не участвовала
conn = pd.read_parquet(ROOT / cfg["paths"]["raw"] / "hackathonlicence" / "connection.parquet")
Drail = G.road_distance(d.ids, conn, "railway")
has = np.isfinite(Drail).sum(1) > 1
Arail = G.knn_graph(np.where(np.isfinite(Drail), -Drail, -1e9), cfg["edges"]["k"])
ext = {}
for m in L.columns:
    y = L[m].values
    obs = graph_icvi(Arail, y)
    perm = [graph_icvi(Arail, rng.permutation(y)) for _ in range(cfg["typology"]["n_perm"])]
    ext[m] = {f"{k}_z": (obs[k] - np.mean([p[k] for p in perm])) / (np.std([p[k] for p in perm]) + 1e-12) * (1 if k != "AVU" else -1)
              for k in ("AVI", "AVU", "MQ")}
E = pd.DataFrame(ext).T
E["mean_z"] = E.mean(1)
E["rank"] = E["mean_z"].rank(ascending=False, method="min").astype(int)
E = E.sort_values("rank")
E.to_csv(M / "external_railway.csv")
print(f"\nВнешняя сеть (ж/д, {int(has.sum())} МО со связями):\n", E.round(2).to_string())
