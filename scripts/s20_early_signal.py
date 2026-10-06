"""Шаг 7г. Ранний сигнал: кто ближе всего к смене типа.

Для каждого МО и месяца — «запас» = сходство с центром своего типа минус сходство с ближайшим чужим центром
(признаки основной типологии, уровень трат — помесячный; центры — по основной типологии, косинус как в KEFRiN-c).
Запас ≤ 0 — МО в этом месяце ближе к чужому типу. Кандидаты — МО с наименьшим средним запасом
за последние 6 месяцев и падающим трендом.

Проверка задним числом: считаем запас только по 2023 году и смотрим, попали ли в 10% МО с наименьшим запасом
те, кто в 2024 году сменил тип насовсем (outputs/dynamics/mo_transitions.csv) — во сколько раз чаще случайного.

Выход: outputs/candidates/{candidates.csv, backtest.json}
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uklad import load_config  # noqa: E402
from uklad import attributes as F  # noqa: E402
from uklad.matrix import load  # noqa: E402

cfg = load_config()
tc = cfg["typology"]
out = ROOT / cfg["paths"]["outputs"] / "candidates"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
ids = np.asarray(d.ids)
O = ROOT / cfg["paths"]["outputs"]
T = pd.read_csv(O / "interpret" / "mo_types.csv").set_index("territory_id").loc[ids]
y = T["type"].values
K = int(y.max()) + 1

mf = F.monthly_features(pd.read_parquet(ROOT / cfg["paths"]["processed"] / "spend.parquet"))
lvl = mf["level"].unstack("month").loc[ids]
months = list(lvl.columns)
raw_lvl = mf["level"].groupby(level=0).mean().loc[ids]
mu, sd = raw_lvl.mean(), raw_lvl.std()
nrm = lambda X: X / np.linalg.norm(X, axis=1, keepdims=True)
Y0 = d.Y[tc["attributes"]].copy()
cent = nrm(np.stack([Y0.values[y == c].mean(0) for c in range(K)]))


def margins(month_cols):
    """Запас по каждому месяцу: N × len(month_cols)."""
    res = []
    for m in month_cols:
        Ym = Y0.copy()
        Ym["level"] = (lvl[m] - mu) / sd
        S = nrm(Ym.values) @ cent.T
        own = S[np.arange(len(y)), y]
        S[np.arange(len(y)), y] = -np.inf
        res.append(own - S.max(1))
    return np.stack(res, 1)


Mg = margins(months)
other = None
last6 = Mg[:, -6:]
slope = np.polyfit(np.arange(6), last6.T, 1)[0]
Ylast = Y0.copy(); Ylast["level"] = (lvl[months[-6:]].mean(1) - mu) / sd
S = nrm(Ylast.values) @ cent.T
S[np.arange(len(y)), y] = -np.inf
names = pd.read_csv(O / "interpret" / "mo_types.csv").set_index("territory_id").loc[ids]
C = pd.DataFrame({"territory_id": ids, "name": names["name"].values, "region": names["region"].values,
                  "type_name": names["type_name"].values, "margin_last6": last6.mean(1), "trend": slope,
                  "closest_other": [names["type_name"].unique()[0]] * len(ids)})
tn = names.drop_duplicates("type").set_index("type")["type_name"]
C["closest_other"] = [tn[k] for k in S.argmax(1)]
C = C[(C.margin_last6 < 0.05) & (C.trend < 0)].sort_values("margin_last6")
C.round(4).to_csv(out / "candidates.csv", index=False)

# проверка задним числом: запас по 2023 → смены насовсем в 2024
tr = pd.read_csv(O / "dynamics" / "mo_transitions.csv")
print(tr.columns.tolist())
key = "kind" if "kind" in tr else tr.columns[1]
moved = set(tr.loc[tr[key].astype(str).str.contains("направ"), "territory_id"]) if "territory_id" in tr else set()
M23 = Mg[:, :12].mean(1)
top = set(ids[np.argsort(M23)[: len(ids) // 10]])
hit = len(top & moved)
base = len(moved) / len(ids)
bt = {"moved_total": len(moved), "top10pct_size": len(top), "moved_in_top10pct": hit,
      "precision": hit / len(top), "base_rate": base, "lift": (hit / len(top)) / base if base else None,
      "recall": hit / len(moved) if moved else None, "candidates_now": int(len(C))}
(out / "backtest.json").write_text(json.dumps(bt, ensure_ascii=False, indent=1), encoding="utf-8")
print(bt)
print(C.head(12).to_string(index=False))
