"""Шаг 7д. Проверки, не замкнутые на собственные признаки модели.

(А) Отложенные признаки (leave-block-out). Типология строится заново без одного блока признаков (зарплата; занятость;
    население и урбанизация; доступность рынков; уровень трат), и проверяется, насколько такие типы объясняют
    отложенный показатель, которого модель не видела (η²), — против случайных разбиений тех же размеров.
(Б) Значимость переходов. Для каждого МО, сменившего тип насовсем, считается «отрыв» к новому типу — разница
    косинусных расстояний до центров старого и нового типа в пространстве KEFRiN (признаки + строка сети) — и его
    скачок до и после точки разрыва. Точка смены выбрана по тем же данным, поэтому статистика — максимум по всем
    точкам разрыва (скан-статистика). Нулевое распределение — та же статистика у МО того же исходного типа, которые
    тип не меняли: так учитывается автокоррелиция помесячных рядов (перемешивание месяцев её разрушает и завышает
    значимость). Поправка на множественность — Бенджамини — Хохберг (FDR 5%).

Выход: outputs/validation/{held_out.csv, transitions_significance.csv, summary.json}
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import tracking as TM  # noqa: E402
from uklad.explain import eta_squared  # noqa: E402
from uklad.matrix import load  # noqa: E402

cfg = load_config()
K, seed, metric = cfg["typology"]["K"], cfg["seed"], cfg["typology"]["metric"]
out = ROOT / cfg["paths"]["outputs"] / "validation"
out.mkdir(parents=True, exist_ok=True)
d = load(cfg)
rng = np.random.default_rng(seed)
P = C.modularity_rows(d.A)
emp = ["emp_agro", "emp_mining", "emp_industry", "emp_transport", "emp_market_services", "emp_public"]

# ---------- (А) отложенные признаки ----------
BLOCKS = {  # блок признаков модели → отложенные показатели (в исходных единицах)
    "зарплата": (["log_wage"], ["wage"]),
    "занятость по отраслям": (emp, emp),
    "население и доля горожан": (["log_pop", "urban_share"], ["population", "urban_share"]),
    "доступность рынков": (["log_market_access"], ["market_access"]),
    "уровень трат": (["level"], ["spend"]),
}
y_main = C.kefrin(d.Y.values, P, K, metric=metric, seed=seed, n_init=10)
rows = []
for block, (drop, held) in BLOCKS.items():
    Yb = d.Y.drop(columns=drop).values
    yb = C.kefrin(Yb, P, K, metric=metric, seed=seed, n_init=10)
    for v in held:
        x = np.log(d.raw[v]) if v in ("population", "spend", "wage", "market_access") else d.raw[v]
        e = eta_squared(x, yb)
        null = [eta_squared(x, rng.permutation(yb)) for _ in range(200)]
        rows.append({"блок убран": block, "показатель": v, "eta2_без_блока": e, "eta2_основная": eta_squared(x, y_main),
                     "eta2_случайно_95": float(np.quantile(null, 0.95)),
                     "p": (1 + sum(n >= e for n in null)) / (1 + len(null))})
    print(block, "готово", flush=True)
H = pd.DataFrame(rows)
H.to_csv(out / "held_out.csv", index=False)
print(H.round(3).to_string())

# ---------- (Б) значимость переходов ----------
months, Ys, As = TM.monthly_inputs(d, cfg["edges"]["k"], cfg["dynamics"]["smooth"])
L = pd.read_csv(ROOT / cfg["paths"]["outputs"] / "dynamics" / "labels_main.csv", index_col=0).values.T   # T × N
rho, xi = C.kefrin_weights(Ys[0], C.modularity_rows(As[0]))


def cosd(a, b):
    return 1 - (a @ b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)


T = len(months)
tr = pd.read_csv(ROOT / cfg["paths"]["outputs"] / "dynamics" / "mo_transitions.csv")
pos = pd.Series(np.arange(len(d.ids)), index=d.ids)
movers = tr[tr.type_start != tr.type_end].reset_index(drop=True)
idx = pos[movers.territory_id].values
ta = np.array([np.bincount(L[:3, i]).argmax() for i in idx])    # тип в начале (мода первых 3 месяцев)
tb = np.array([np.bincount(L[-3:, i]).argmax() for i in idx])   # тип в конце
# нулевая выборка: МО, не менявшие тип за 24 месяца, — для каждой пары (a → b) до 600 МО типа a и их «отрыв» к b.
# Так сохраняется настоящая автокорреляция помесячных рядов (сглаживание, сезон), чего не даёт перемешивание месяцев
stable = np.where((L == L[0]).all(0))[0]
pairs = sorted(set(zip(ta, tb)))
pool = {pr: rng.choice(stable[L[0, stable] == pr[0]], size=min(600, (L[0, stable] == pr[0]).sum()), replace=False)
        for pr in pairs}
Mg = np.empty((T, len(idx)))
Mn = {pr: np.empty((T, len(pool[pr]))) for pr in pairs}
for t in range(T):                                              # по месяцу за раз: матрица сети одна в памяти
    Yt, Pt = Ys[t], np.asarray(C.modularity_rows(As[t]))
    cent = {k: np.r_[np.sqrt(rho) * Yt[L[t] == k].mean(0), np.sqrt(xi) * Pt[L[t] == k].mean(0)] for k in np.unique(L[t])}
    zz = lambda i: np.r_[np.sqrt(rho) * Yt[i], np.sqrt(xi) * Pt[i]]
    for j, i in enumerate(idx):
        z = zz(i)
        Mg[t, j] = cosd(z, cent[ta[j]]) - cosd(z, cent[tb[j]])   # > 0 — МО ближе к новому типу
    for pr in pairs:
        for q, i in enumerate(pool[pr]):
            z = zz(i)
            Mn[pr][t, q] = cosd(z, cent[pr[0]]) - cosd(z, cent[pr[1]])
    del Pt


def scan(x):
    return max(x[s:].mean() - x[:s].mean() for s in range(3, T - 2))


null_scan = {pr: np.array([scan(Mn[pr][:, q]) for q in range(Mn[pr].shape[1])]) for pr in pairs}
res = []
for j, r in movers.iterrows():
    obs = scan(Mg[:, j])
    nl = null_scan[(ta[j], tb[j])]
    res.append({"territory_id": r.territory_id, "name": r["name"], "region": r.region, "from": r.type_start,
                "to": r.type_end, "shift": obs, "null_n": len(nl), "p": (1 + (nl >= obs).sum()) / (1 + len(nl))})
S = pd.DataFrame(res).sort_values("p")
# Бенджамини — Хохберг
n = len(S)
q = (S.p.values * n / np.arange(1, n + 1))
S["q_BH"] = np.minimum.accumulate(q[::-1])[::-1].clip(max=1)
S["значим_FDR5"] = S.q_BH <= 0.05
S.to_csv(out / "transitions_significance.csv", index=False)

summary = {
    "held_out_all_above_random": bool((H.eta2_без_блока > H.eta2_случайно_95).all()),
    "held_out_wage_eta2": float(H.loc[H.показатель == "wage", "eta2_без_блока"].iloc[0]),
    "held_out_wage_eta2_main": float(H.loc[H.показатель == "wage", "eta2_основная"].iloc[0]),
    "held_out_emp_eta2_mean": float(H.loc[H.показатель.isin(emp), "eta2_без_блока"].mean()),
    "transitions_tested": int(n), "transitions_significant": int(S["значим_FDR5"].sum()),
    "transitions_p05": int((S.p <= 0.05).sum()),
    "transitions_p05_expected": 0.05 * n,
    # совокупно: больше ли значимых по отдельности, чем дала бы случайность (биномиальный тест)
    "transitions_binom_p": float(__import__("scipy.stats", fromlist=["binomtest"]).binomtest(int((S.p <= 0.05).sum()), n, 0.05, alternative="greater").pvalue),
    # медианный «отрыв» сменивших тип против медианы у не менявших
    "shift_median_movers": float(S["shift"].median()),
    "shift_median_stable": float(np.median(np.concatenate(list(null_scan.values())))),
}
json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
