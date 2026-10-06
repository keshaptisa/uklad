"""Шаг 5. Динамика типов по 24 месячным атрибутированным сетям: сравнение способов отслеживания и итоговые переходы.

Выход: outputs/dynamics/{variants.csv, monthly_icvi.csv, labels_<variant>.csv, transitions.csv,
       persistent_switches.csv, monic_2023-01_2024-12.csv}
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import tracking as TM  # noqa: E402
from uklad.matrix import load  # noqa: E402
from uklad.quality import feature_icvi, graph_icvi  # noqa: E402

cfg = load_config()
dc, K, seed = cfg["dynamics"], cfg["typology"]["K"], cfg["seed"]
out = ROOT / cfg["paths"]["outputs"] / "dynamics"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
y0 = C.kefrin(d.Y.values, C.modularity_rows(d.A), K, seed=seed, n_init=10, metric=cfg["typology"]["metric"])
months, Ys, As = TM.monthly_inputs(d, cfg["edges"]["k"], dc["smooth"])
rho, xi = C.kefrin_weights(Ys[0], C.modularity_rows(As[0]))
print(f"месяцев {len(months)}, ρ={rho}, ξ={xi:.4f}", flush=True)

variants = {"независимо по месяцам": TM.independent_kefrin(Ys, As, K, y0, rho, xi, seed, metric=cfg["typology"]["metric"])}
for a in dc["alphas"]:
    variants[f"эволюционный KEFRiN, α={a}"] = TM.evolutionary_kefrin(Ys, As, K, a, y0, rho, xi, seed, metric=cfg["typology"]["metric"])
LA, alphas_t = TM.affect_kefrin(Ys, As, K, y0, rho, xi, seed, metric=cfg["typology"]["metric"])
variants["эволюционный KEFRiN, адаптивный α (AFFECT)"] = LA
pd.DataFrame({"month": months, "alpha": alphas_t}).to_csv(out / "affect_alpha.csv", index=False)
print("AFFECT α_t:", np.round(alphas_t, 2), flush=True)
for w in dc["omegas"]:
    L = C.temporal_leiden(As, omega=w, seed=seed)
    variants[f"temporal Leiden, ω={w}"] = L
    print("temporal Leiden", w, "сообществ:", len(np.unique(L)), flush=True)

def slug(name: str) -> str:
    """ASCII-имя файла для варианта отслеживания (переносимо между ОС)."""
    if name.startswith("независимо"):
        return "independent"
    if "AFFECT" in name:
        return "evolutionary_affect"
    if name.startswith("эволюционный"):
        return "evolutionary_alpha" + name.split("α=")[1]
    if name.startswith("temporal Leiden"):
        return "temporal_leiden_omega" + name.split("ω=")[1]
    raise ValueError(name)


rows, mon = [], []
for name, L in variants.items():
    s = TM.dynamics_summary(L, dc["min_run"])
    q = [{**feature_icvi(Ys[t], L[t], sample=None), **graph_icvi(As[t], L[t]), "month": months[t], "variant": name}
         for t in range(len(months))]
    qd = pd.DataFrame(q)
    mon.append(qd)
    s.update({f"{m}_median": qd[m].median() for m in ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]})
    s.update({"variant": name, "K": len(np.unique(L))})
    rows.append(s)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()}, flush=True)
    pd.DataFrame(L.T, index=d.ids, columns=months).to_csv(out / f"labels_{slug(name)}.csv")

pd.DataFrame(rows).set_index("variant").to_csv(out / "variants.csv")
pd.concat(mon).to_csv(out / "monthly_icvi.csv", index=False)

main = variants[f"эволюционный KEFRiN, α={dc['alpha']}"]
pd.DataFrame(main.T, index=d.ids, columns=months).to_csv(out / "labels_main.csv")
pd.DataFrame(TM.transition_matrix(main, K)).to_csv(out / "transitions.csv")
ps = TM.persistent_switches(main, dc["min_run"])
ps["territory_id"] = d.ids[ps.i.values]
ps["month"] = [months[t] for t in ps.t_switch]
ps.to_csv(out / "persistent_switches.csv", index=False)
ev = TM.monic_events(main[0], main[-1])
ev.to_csv(out / f"monic_{months[0]}_{months[-1]}.csv", index=False)
print(ev.to_string())
print("устойчивых переходов:", len(ps))
