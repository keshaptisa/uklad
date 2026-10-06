"""Шаг 8б. Данные лендинга: site_src/data/site.json (все результаты в одном компактном файле)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import attributes as F  # noqa: E402
from uklad.matrix import load  # noqa: E402

cfg = load_config()
O = ROOT / cfg["paths"]["outputs"]
T = yaml.safe_load(open(ROOT / "configs" / "typology.yaml", encoding="utf-8"))
d = load(cfg)
mt = pd.read_csv(O / "interpret" / "mo_types.csv", index_col=0).loc[d.ids]
K = int(mt.type.max()) + 1
spend = pd.read_parquet(ROOT / cfg["paths"]["processed"] / "spend.parquet")
w = F.spend_cube(spend)
sh = F.shares(w)
months = sorted(w.index.get_level_values(1).unique())


def series(s, scale=1, nd=0):
    u = s.unstack("month").loc[d.ids, months] * scale
    return np.round(u.values, nd).astype(int if nd == 0 else float).tolist()


# помесячные типы: эволюционный KEFRiN, если посчитан, иначе - статический тип
p = O / "dynamics" / "labels_main.csv"
if p.exists():
    L = pd.read_csv(p, index_col=0).loc[d.ids]
    # согласуем номера помесячных типов с каноническими (по большинству)
    M = pd.crosstab(L.values.ravel(), np.repeat(mt.type.values, L.shape[1]))
    from scipy.optimize import linear_sum_assignment
    r, c = linear_sum_assignment(-M.values)
    mp = {M.index[i]: M.columns[j] for i, j in zip(r, c)}
    tm = L.apply(lambda col: col.map(mp)).values
else:
    tm = np.repeat(mt.type.values[:, None], len(months), 1)

# экономические двойники: 3 ближайших МО из других регионов в пространстве атрибутов
Y = d.Y.values
reg = d.mo.region_name.to_numpy(dtype=object)
D = ((Y[:, None, :] - Y[None, :, :]) ** 2).sum(-1)
D[reg[:, None] == reg[None, :]] = np.inf
twins = np.argsort(D, axis=1)[:, :3]

rh = pd.read_csv(O / "rhythm" / "mo_rhythm.csv", index_col=0).reindex(d.ids)
mo = {
    "id": d.ids.tolist(), "name": d.mo.name.tolist(), "region": d.mo.region_name.tolist(),
    "kind": d.mo.mo_type.tolist(), "t": mt.type.tolist(), "tm": ["".join(map(str, r)) for r in tm],
    "spend": series(w["total"], 1 / 10),  # десятки рублей
    "food": series(sh["food"], 1000), "cafe": series(sh["cafe"], 1000), "market": series(sh["market"], 1000),
    "wage": np.round(d.mo.wage.fillna(-1)).astype(int).tolist(),
    "pop": np.round(d.mo.population.fillna(-1)).astype(int).tolist(),
    "urban": np.round(d.mo.urban_share.fillna(-1) * 100).astype(int).tolist(),
    "access": np.round(d.mo.market_access.fillna(-1)).astype(int).tolist(),
    "emp": np.round(d.mo[["emp_agro", "emp_mining", "emp_industry", "emp_transport", "emp_market_services", "emp_public"]]
                    .fillna(-0.01).values * 100).astype(int).tolist(),
    "citywide": d.mo.context_citywide.astype(int).tolist(),
    "rt": rh.rhythm_type.fillna(-1).astype(int).tolist(),
    "twins": twins.tolist(),
}

raw = d.raw
types = []
fca = pd.read_csv(O / "interpret" / "fca.csv")
ex = pd.read_csv(O / "interpret" / "examples.csv")
for k in range(K):
    m = mt.type.values == k
    f = fca[fca.type == k].assign(score=lambda x: x.precision * x.coverage).sort_values("score", ascending=False)
    types.append({
        "k": k, "name": T["names"][k], "short": T["short"][k], "n": int(m.sum()),
        "med": {c: round(float(raw.loc[m, c].median()), 1) for c in raw.columns},
        "fca": [{"d": r.description, "p": round(r.precision, 2), "c": round(r.coverage, 2), "s": round(r.stability, 2)}
                for r in f.head(2).itertuples()],
        "largest": ex.loc[ex.type == k, "largest"].iloc[0], "regions": ex.loc[ex.type == k, "top_regions"].iloc[0],
    })
nat = {c: round(float(raw[c].median()), 1) for c in raw.columns}


def csv(path, **kw):
    return pd.read_csv(path, **kw) if path.exists() else None


out = {
    "mainMethod": "KEFRiN-c (признаки+сеть)" if cfg["typology"]["metric"] == "cosine" else "KEFRiN-e (признаки+сеть)",
    "months": months, "K": K, "types": types, "national": nat,
    "natSpend": np.round(w["total"].groupby(level="month").median().loc[months].values).astype(int).tolist(),
    "mo": mo,
    "rhythm": {"names": T["rhythm_names"], "short": T["rhythm_short"],
               "profiles": {}, "n": {}},
}
prof = pd.read_csv(O / "rhythm" / "profiles.csv", header=[0, 1], index_col=0)
for k in prof.index:
    out["rhythm"]["profiles"][int(k)] = {c: np.round(prof.loc[k, c].values * 100, 1).tolist() for c in ["total", "cafe"]}
    out["rhythm"]["n"][int(k)] = int((rh.rhythm_type == int(k)).sum())
tr = pd.read_csv(O / "dynamics" / "mo_transitions.csv", index_col=0).reindex(d.ids)
mo["kind"] = tr["kind"].fillna("без смен").tolist()
mo["lvlchg"] = np.round(tr["level_change_pct"].fillna(0), 1).tolist()
out["directed"] = json.loads(pd.read_csv(O / "dynamics" / "directed_by_pair.csv").round(1).to_json(orient="records", force_ascii=False))
out["trSummary"] = json.load(open(O / "dynamics" / "transitions_summary.json", encoding="utf-8"))
syn = ROOT / cfg["paths"]["outputs"] / "synthetic" / "summary.csv"
if syn.exists():
    out["synthetic"] = json.loads(pd.read_csv(syn).round(3).to_json(orient="records", force_ascii=False))
for name, path in {"methods": O / "method_comparison" / "ranking.csv", "methodsRaw": O / "method_comparison" / "icvi_raw.csv", "methodsZ": O / "method_comparison" / "icvi_z.csv",
                   "chooseK": O / "choose_k" / "summary.csv", "edges": O / "edges" / "summary.csv",
                   "dynVariants": O / "dynamics" / "variants.csv"}.items():
    t = csv(path) if name == "chooseK" else csv(path, index_col=0)
    if t is not None:
        out[name] = json.loads(t.round(4).to_json(orient="split"))
# дополнительные проверки (scripts/s13_checks.py): варианты рейтинга, отпечатки типов, расхождение типов во времени
for name, path in {"rankVariants": O / "method_comparison" / "ranking_variants.csv", "fingerprint": O / "interpret" / "fingerprint.csv",
                   "divergence": O / "interpret" / "divergence.csv"}.items():
    t = csv(path, index_col=0)
    if t is not None:
        out[name] = json.loads(t.round(3).to_json(orient="split", force_ascii=False))
dv = O / "interpret" / "divergence_summary.json"
if dv.exists():
    out["divSummary"] = json.load(open(dv, encoding="utf-8"))
# сеть: раскладка и 3 сильнейших ребра у каждого МО (scripts/s14_network_layout.py), индексы - в порядке out["mo"]["id"]
NW = O / "network"
if (NW / "layout.csv").exists():
    pos_of = {int(r.territory_id): (r.x, r.y) for r in pd.read_csv(NW / "layout.csv").itertuples()}
    order = {int(t): k for k, t in enumerate(out["mo"]["id"])}
    out["net"] = {"xy": [list(pos_of.get(int(t), (None, None))) for t in out["mo"]["id"]],
                  "e": [[order[int(a)], order[int(b)]] for a, b in pd.read_csv(NW / "edges.csv").itertuples(index=False)
                        if int(a) in order and int(b) in order],
                  "summary": json.load(open(NW / "summary.json", encoding="utf-8"))}
# таблица «МО → тип» для кнопки «Скачать CSV» на лендинге
mt = csv(O / "interpret" / "mo_types.csv")
if mt is not None:
    cols = [c for c in ["territory_id", "name", "region", "mo_type", "type", "type_name", "spend", "wage", "population"] if c in mt]
    out["csvTypes"] = mt[cols].round(1).to_csv(index=False)
outdir = ROOT / "site_src" / "data"
s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
(outdir / "site.json").write_text(s, encoding="utf-8")
print(f"site.json: {len(s) / 1e6:.2f} МБ; помесячные типы из {'динамики' if p.exists() else 'статики'}")
