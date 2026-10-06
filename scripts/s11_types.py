"""Шаг 7. Интерпретация основной типологии: профили по Миркину, FCA-описания, паттерны OIPC, внешняя проверка.

Выход: outputs/interpret/{mo_types.csv, profile_median.csv, mirkin_dev.csv, mirkin_contrib.csv, fca.csv,
       oipc_patterns.csv, oipc_by_type.csv, external_eta2.csv, examples.csv}
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import explain as I  # noqa: E402
from uklad.matrix import load  # noqa: E402

cfg = load_config()
K, seed = cfg["typology"]["K"], cfg["seed"]
out = ROOT / cfg["paths"]["outputs"] / "interpret"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)

y = C.kefrin(d.Y.values, C.modularity_rows(d.A), K, seed=seed, n_init=10, metric=cfg["typology"]["metric"])
# канонический порядок типов: по медианным тратам на жителя (0 — самые высокие)
order = d.raw.groupby(y)["spend"].median().sort_values(ascending=False).index
y = pd.Series(y).map({old: new for new, old in enumerate(order)}).values

names_file = ROOT / "configs" / "typology.yaml"
tnames = yaml.safe_load(open(names_file, encoding="utf-8"))["names"] if names_file.exists() else {}
tname = lambda k: tnames.get(k, f"тип {k}")

raw = d.raw.copy()
raw["engel_residual"] = d.monthly["engel"].groupby(level=0).mean().loc[d.ids].values * 100
mt = pd.DataFrame({"name": d.mo.name, "region": d.mo.region_name, "mo_type": d.mo.mo_type, "type": y,
                   "type_name": [tname(k) for k in y], "lat": d.mo.lat, "lon": d.mo.lon}, index=d.ids)
mt.index.name = "territory_id"
mt.join(raw).to_csv(out / "mo_types.csv")

prof = raw.groupby(y).median()
prof.insert(0, "n", np.bincount(y))
prof.index = [tname(k) for k in prof.index]
prof.to_csv(out / "profile_median.csv")
print(prof.round(1).T.to_string())

dev, contrib = I.mirkin_profile(raw.drop(columns=["engel_residual"]), d.Y, y)
dev.index = contrib.index = [tname(k) for k in dev.index]
dev.to_csv(out / "mirkin_dev.csv")
contrib.to_csv(out / "mirkin_contrib.csv")
print("\nВклад признаков в объяснённый разброс, % (Миркин):\n", contrib.round(1).to_string())

# FCA: шкалированные показатели + административные бинарные признаки
extra = pd.DataFrame({"городской округ": d.mo.mo_type.str.contains("городской округ|внутригородск", case=False, na=False),
                      "административный центр региона": d.mo.mo_status.fillna("").str.contains("административный_центр")},
                     index=d.ids)
fca_raw = raw[["spend", "share_food", "share_cafe", "share_market", "wage", "population", "urban_share",
               "market_access", "emp_agro", "emp_mining", "emp_industry", "emp_transport", "emp_market_services", "emp_public"]]
RU = {"spend": "траты на жителя", "share_food": "доля продовольствия", "share_cafe": "доля общепита",
      "share_market": "доля маркетплейсов", "wage": "зарплата", "population": "население", "urban_share": "доля горожан",
      "market_access": "доступность рынков", "emp_agro": "занятость в сельском хозяйстве", "emp_mining": "занятость в добыче",
      "emp_industry": "занятость в промышленности", "emp_transport": "занятость в транспорте", "emp_market_services": "занятость в рыночных услугах",
      "emp_public": "занятость в бюджетном секторе"}
M = I.scale_context(fca_raw.rename(columns=RU), extra)
rng = np.random.default_rng(seed)
fca = pd.DataFrame([r for k in range(K) for r in I.fca_describe(M, y, k, rng=rng)])
fca["type_name"] = fca["type"].map(tname)
fca.to_csv(out / "fca.csv", index=False)
print("\nFCA:\n", fca[["type_name", "description", "precision", "coverage", "stability"]].round(2).to_string())

# OIPC: порядок долей пяти категорий, нормированных ранг-процентилем по всем МО
shares = raw[["share_food", "share_market", "share_transport", "share_health", "share_cafe"]].rank(pct=True)
shares.columns = ["продовольствие", "маркетплейсы", "транспорт", "здоровье", "общепит"]
pat = I.oipc(shares, eps=cfg["interpret"]["oipc_eps"])
pt = pd.DataFrame({"pattern": pat, "type": y})
sizes = pat.value_counts()
big = sizes[sizes >= cfg["interpret"]["oipc_min_size"]].index
pnames = {p: I.pattern_name(shares, pat.index[pat == p]) for p in big}
pp = pd.DataFrame({"pattern": big, "n": sizes[big].values, "order": [pnames[p] for p in big]})
pp.to_csv(out / "oipc_patterns.csv", index=False)
ct = pd.crosstab(pt["type"].map(tname), pt["pattern"].where(pt["pattern"].isin(big), -1))
ct.to_csv(out / "oipc_by_type.csv")
from sklearn.metrics import adjusted_mutual_info_score as AMI  # noqa: E402
print(f"\nOIPC: паттернов всего {pat.nunique()}, крупных (≥{cfg['interpret']['oipc_min_size']} МО) {len(big)}, "
      f"покрывают {sizes[big].sum() / len(pat):.0%} МО; AMI с типами {AMI(y, pat):.3f}")
for p in big[:8]:
    m = pat == p
    print(f"  паттерн {p} ({m.sum()} МО): {pnames[p]} | типы: {pd.Series(y[m.values]).map(tname).value_counts().head(3).to_dict()}")

# внешняя проверка: показатели, не входившие в атрибуты, и индекс мобильности СберИндекса
ext = {c: raw[c] for c in ["share_food", "share_cafe", "share_market", "share_transport", "share_health", "engel_residual"]}
mob = pd.read_parquet(ROOT / cfg["paths"]["raw"] / "indeks-mobilnosti.parquet")
mob = mob[mob.period == mob.period.min()].set_index("ref_area")["value"]
full = d.mo.name_full
match = full.map(mob)
print(f"\nиндекс мобильности сопоставлен по полному названию: {match.notna().sum()} МО из {len(mob)}")
ext["mobility_index"] = match
# контроль: типы только по экономической базе Росстата (k-means без уровня трат и без сети) — модель не видит трат вовсе
y_base = C.kmeans(d.Y.drop(columns=["level"]).values, K, seed=seed)
eta = pd.DataFrame({"eta2": {k: I.eta_squared(v, y) for k, v in ext.items()},
                    "eta2_base_only": {k: I.eta_squared(v, y_base) for k, v in ext.items()},
                    "n": {k: int(pd.Series(v).notna().sum()) for k, v in ext.items()}})
eta.to_csv(out / "external_eta2.csv")
print(eta.round(3).to_string())
if match.notna().sum() > 30:
    mob_by_type = pd.Series(match.values).groupby(y).median().rename(index=tname)
    mob_by_type.rename("mobility_km_median").to_csv(out / "mobility_by_type.csv")
    print(mob_by_type.round(2).to_string())

# примеры: крупнейшие МО и самые типичные (ближе всех к центру типа)
rows = []
for k in range(K):
    m = y == k
    Yk = d.Y.values[m]
    dist = ((Yk - Yk.mean(0)) ** 2).sum(1)
    sub = d.mo[m]
    rows.append({"type": k, "type_name": tname(k), "n": int(m.sum()),
                 "largest": ", ".join(sub.sort_values("population", ascending=False).name.head(6)),
                 "typical": ", ".join(sub.name.iloc[np.argsort(dist)[:6]]),
                 "top_regions": "; ".join(f"{r} ({n})" for r, n in sub.region_name.value_counts().head(4).items())})
ex = pd.DataFrame(rows)
ex.to_csv(out / "examples.csv", index=False)
print(ex.to_string())
