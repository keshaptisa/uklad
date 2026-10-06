"""Шаг 5б. Разбор переходов МО между типами: направленные и возвратные («сезонные качели»).

Правило «новый тип держится ≥ 3 месяцев» отсекает шум, но не сезонность: северный МО может полгода жить как
«отдалённый центр» и вернуться в «крупные города» к декабрю. Поэтому для каждого МО со сменами:
- направленный переход — тип в декабре 2024 ≠ тип в январе 2023 (с поправкой на первые и последние 3 месяца — берём моду);
- возвратный — МО ушёл и вернулся в исходный тип.
Плюс что изменилось у направленных: относительный уровень трат и структура корзины до и после.

Выход: outputs/dynamics/{mo_transitions.csv, directed_by_pair.csv, transitions_summary.json}
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad.matrix import load  # noqa: E402
from uklad.tracking import persistent_switches  # noqa: E402

cfg = load_config()
O = ROOT / cfg["paths"]["outputs"] / "dynamics"
names = yaml.safe_load(open(ROOT / "configs" / "typology.yaml", encoding="utf-8"))["names"]
d = load(cfg)
mt = pd.read_csv(ROOT / cfg["paths"]["outputs"] / "interpret" / "mo_types.csv", index_col=0).loc[d.ids]
L = pd.read_csv(O / "labels_main.csv", index_col=0).loc[d.ids]
# номера типов динамики → канонические номера (по наибольшему совпадению)
M = pd.crosstab(L.values.ravel(), np.repeat(mt.type.values, L.shape[1]))
r, c = linear_sum_assignment(-M.values)
mp = {M.index[i]: M.columns[j] for i, j in zip(r, c)}
Lc = L.apply(lambda col: col.map(mp)).values  # N × T
months = list(L.columns)

mode = lambda a: pd.Series(a).mode().iloc[0]
start = np.array([mode(row[:3]) for row in Lc])
end = np.array([mode(row[-3:]) for row in Lc])
nsw = (Lc[:, 1:] != Lc[:, :-1]).sum(1)
kind = np.where(nsw == 0, "без смен", np.where(start != end, "направленный", "возвратный"))

lvl = d.monthly["level"].unstack().loc[d.ids, months].values
cafe = d.raw  # для подписи
mo = pd.DataFrame({"name": d.mo.name.values, "region": d.mo.region_name.values,
                   "type_start": [names[k] for k in start], "type_end": [names[k] for k in end], "switches": nsw, "kind": kind,
                   "level_2023_h1": lvl[:, :6].mean(1), "level_2024_h2": lvl[:, -6:].mean(1)}, index=d.ids)
mo["level_change_pct"] = (np.exp(mo.level_2024_h2 - mo.level_2023_h1) - 1) * 100
mo.index.name = "territory_id"
mo.to_csv(O / "mo_transitions.csv")

ps = persistent_switches(Lc.T, cfg["dynamics"]["min_run"])
dirm = mo[mo.kind == "направленный"]
pairs = dirm.groupby(["type_start", "type_end"]).agg(n=("name", "size"), examples=("name", lambda s: ", ".join(s.head(6))),
                                                      level_change_pct=("level_change_pct", "median")).sort_values("n", ascending=False)
pairs.to_csv(O / "directed_by_pair.csv")
summary = {"mo_with_switches": int((nsw > 0).sum()), "directed": int((kind == "направленный").sum()),
           "returning": int((kind == "возвратный").sum()), "persistent_events": int(len(ps)),
           "directed_level_change_median_pct": float(dirm.level_change_pct.median()),
           "all_level_change_median_pct": float(mo.level_change_pct.median()),
           "directed_by_region": dirm.region.value_counts().head(5).to_dict()}
json.dump(summary, open(O / "transitions_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
print(pairs.to_string())
