"""Шаг 10. Отчёт: report/uklad_methodology_src.md + таблицы из outputs/ → report/uklad_methodology.md, .html, .pdf.

Таблицы не вписываются руками: метки {{...}} в тексте заменяются таблицами из результатов шагов,
поэтому числа в отчёте всегда совпадают с outputs/. PDF печатается установленным Chrome или Edge (headless).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml
from markdown_it import MarkdownIt

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "outputs"
R = ROOT / "report"
T = yaml.safe_load(open(ROOT / "configs" / "typology.yaml", encoding="utf-8"))


def num(v, d=3):
    if pd.isna(v):
        return "—"
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def md_table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(str(x) for x in r) + " |" for r in df.values)


def t_methods():
    r = pd.read_csv(O / "method_comparison" / "ranking.csv", index_col=0)
    raw = pd.read_csv(O / "method_comparison" / "icvi_raw.csv", index_col=0)
    rows = []
    for m in r.index:
        rows.append([m, int(r.loc[m, "rank_threshold"]), int(r.loc[m, "rank_borda"]), num(raw.loc[m, "SW"]), num(raw.loc[m, "CH"], 0),
                     num(raw.loc[m, "S_Dbw"]), num(raw.loc[m, "AVI"]), num(raw.loc[m, "AVU"]), num(raw.loc[m, "MQ"]),
                     num(raw.loc[m, "bootstrap_ARI"], 2)])
    return md_table(pd.DataFrame(rows, columns=["Метод", "место (Алескеров)", "место (Борда)", "SW ↑", "CH ↑", "S_Dbw ↓",
                                                "AVI ↑", "AVU ↓", "MQ ↑", "бутстрап ↑"]))


def t_methods_z():
    r = pd.read_csv(O / "method_comparison" / "ranking.csv", index_col=0)
    z = pd.read_csv(O / "method_comparison" / "icvi_z.csv", index_col=0)
    cols = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]
    rows = [[m] + [num(z.loc[m, c], 1) for c in cols] for m in r.index]
    return md_table(pd.DataFrame(rows, columns=["Метод"] + [f"z {c}" for c in cols]))


def t_choose_k():
    s = pd.read_csv(O / "choose_k" / "summary.csv")
    rows = [[int(r.K), num(r.SW), num(r.CH, 0), num(r.S_Dbw), num(r.AVI), num(r.AVU), num(r.MQ), num(r.boot_ARI, 2),
             num(r.hennig_min, 2), int(r.n_stable_085)] for r in s.itertuples()]
    return md_table(pd.DataFrame(rows, columns=["K", "SW", "CH", "S_Dbw", "AVI", "AVU", "MQ", "бутстрап ARI",
                                                "худший тип (Хенниг)", "типов со строгим Жаккаром > 0,85"]))


RULES = {"cosine": "косинус профиля трат", "rbf": "гауссово ядро", "corr": "корреляция рядов", "lagcorr": "лаговая корреляция ±2 мес.",
         "dtw": "**DTW траекторий (основное)**", "road": "близость по дорогам", "context": "сходство экономической базы (контроль)", "snf": "слияние SNF: траты + база + дороги",
         "без сети (k-means)": "без сети (k-means)"}


def t_edges():
    e = pd.read_csv(O / "edges" / "summary.csv", index_col=0)
    rows = [[RULES[i], num(r.within_region * 100, 0) + "%", num(r.homoph_log_wage, 2), num(r.homoph_level, 2),
             num(r.homoph_clr_market, 2), num(r.homoph_emp_mining, 2), num(r.leiden_Q, 2)] for i, r in e.iterrows()]
    return md_table(pd.DataFrame(rows, columns=["Правило", "рёбер внутри региона", "похожесть соседей: зарплата", "уровень трат",
                                                "доля маркетплейсов", "занятость в добыче", "модулярность"]))


def t_edge_effect():
    e = pd.read_csv(O / "edge_effect" / "by_rule.csv", index_col=0)
    rows = [[RULES.get(i, i), num(r.ARI_with_main, 2), num(r.ARI_with_region, 2), num(r.SW), num(r.AVI), num(r.MQ)]
            for i, r in e.iterrows()]
    return md_table(pd.DataFrame(rows, columns=["Граф в KEFRiN", "ARI с основной типологией", "ARI с регионом",
                                                "SW", "AVI (свой граф)", "MQ (свой граф)"]))


def t_profiles():
    p = pd.read_csv(O / "interpret" / "profile_median.csv", index_col=0)
    rows = [[i, int(r.n), num(r.spend, 0), num(r.share_food, 1), num(r.share_cafe, 1), num(r.share_market, 1), num(r.wage, 0),
             num(r.population, 0), num(r.urban_share, 0), num(r.market_access, 0), num(r.emp_agro, 1), num(r.emp_mining, 1),
             num(r.emp_industry, 1), num(r.emp_public, 1)] for i, r in p.iterrows()]
    return md_table(pd.DataFrame(rows, columns=["Тип (медианы)", "МО", "траты, ₽/мес", "еда, %", "общепит, %", "маркетпл., %",
                                                "зарплата, ₽", "население", "горожане, %", "доступность", "с/х, %", "добыча, %",
                                                "промышл., %", "бюджет, %"]))


def t_fca():
    f = pd.read_csv(O / "interpret" / "fca.csv")
    f["score"] = f.precision * f.coverage
    best = f.sort_values("score", ascending=False).groupby("type").head(1).sort_values("type")
    rows = [[r.type_name, r.description.replace(" И ", " **и** "), num(r.precision * 100, 0) + "%", num(r.coverage * 100, 0) + "%",
             num(r.stability, 2)] for r in best.itertuples()]
    return md_table(pd.DataFrame(rows, columns=["Тип", "Формула типа", "точность", "покрытие", "устойчивость"]))


def t_eta():
    e = pd.read_csv(O / "interpret" / "external_eta2.csv", index_col=0)
    lab = {"share_food": "доля продовольствия", "share_cafe": "доля общепита", "share_market": "доля маркетплейсов",
           "share_transport": "доля транспорта", "share_health": "доля здоровья", "engel_residual": "отклонение от кривой Энгеля",
           "mobility_index": "индекс покупательской мобильности (СберИндекс)"}
    rows = [[lab[i], num(r.eta2, 2), num(r.eta2_base_only, 2), int(r.n)] for i, r in e.iterrows()]
    return md_table(pd.DataFrame(rows, columns=["Показатель", "η², итоговые типы", "η², типы только по Росстату", "МО"]))


def t_dynamics():
    v = pd.read_csv(O / "dynamics" / "variants.csv", index_col=0)
    rows = [[i, num(r.AMI_adjacent), num(r.switch_rate_month * 100, 2) + "%", num(r.never_switch * 100, 1) + "%",
             int(r.persistent_switches), num(r.persistent_share_of_all * 100, 0) + "%", num(r.SW_median), num(r.MQ_median), int(r.K)]
            for i, r in v.iterrows()]
    return md_table(pd.DataFrame(rows, columns=["Способ", "AMI соседних месяцев", "смен в месяц", "МО без смен", "устойчивых переходов",
                                                "доля устойчивых", "SW (медиана)", "MQ (медиана)", "типов"]))


def t_rhythm():
    t = pd.read_csv(O / "rhythm" / "types.csv")
    rows = [[T["rhythm_names"][int(r.rhythm_type)], int(r.n), int(r.peak_month_total), num(r.amp_total * 100, 0) + "%",
             r.top_regions, r.examples] for r in t.itertuples()]
    return md_table(pd.DataFrame(rows, columns=["Ритм", "МО", "месяц пика", "размах трат (пик − спад)", "регионы", "примеры (самые повторяемые)"]))


def t_directed():
    t = pd.read_csv(O / "dynamics" / "directed_by_pair.csv")
    rows = [[f"{r.type_start} → {r.type_end}", int(r.n), ("+" if r.level_change_pct > 0 else "") + num(r.level_change_pct, 1) + "%",
             r.examples] for r in t.itertuples()]
    return md_table(pd.DataFrame(rows, columns=["Направленный переход", "МО", "изменение уровня трат (медиана)", "примеры"]))


def t_synthetic():
    t = pd.read_csv(O / "synthetic" / "summary.csv")
    rows = [[r["сценарий"], r["вариант"], num(r["NMI"], 2), num(r["ложные смены (не мигранты)"], 2),
             num(r["мигранты найдены через 0 мес."] * 100, 0) + "%", num(r["мигранты найдены через 2 мес."] * 100, 0) + "%",
             num(r["мигранты найдены через 4 мес."] * 100, 0) + "%"] for _, r in t.iterrows()]
    return md_table(pd.DataFrame(rows, columns=["Шум", "Способ", "NMI с истиной", "ложных смен на МО", "мигранты найдены сразу",
                                                "через 2 мес.", "через 4 мес."]))


src = (R / "uklad_methodology_src.md").read_text(encoding="utf-8")
trs = json.load(open(O / "dynamics" / "transitions_summary.json", encoding="utf-8"))
ee = json.load(open(O / "edge_effect" / "summary.json", encoding="utf-8"))
def t_variants():
    V = pd.read_csv(O / "method_comparison" / "ranking_variants.csv", index_col=0)
    return md_table(V.drop(columns=["лучшее место", "худшее место"]).rename_axis("Метод").reset_index())


def t_gap():
    s = json.load(open(O / "interpret" / "divergence_summary.json", encoding="utf-8"))
    rows = [{"Тип": t, "2023, % к медиане России": num(s["gap_pct_2023"][t], 1), "2024": num(s["gap_pct_2024"][t], 1)}
            for t in sorted(s["gap_pct_2024"], key=lambda t: -s["gap_pct_2024"][t])]
    return md_table(pd.DataFrame(rows))


def t_rhythm_cats():
    t = pd.read_csv(O / "rhythm" / "peak_by_category.csv")
    for c in t.columns:
        if c.endswith(", %"):
            t[c] = t[c].map(lambda x: ("+" if x > 0 else "") + num(x, 1))
    for c in ["добыча > 5% занятых, доля МО", "то же по стране"]:
        t[c] = t[c].map(lambda x: num(x * 100, 0) + "%")
    return md_table(t)


subs = {"{{methods_z}}": t_methods_z, "{{rhythm_cats}}": t_rhythm_cats, "{{variants}}": t_variants, "{{gap}}": t_gap, "{{methods}}": t_methods, "{{choose_k}}": t_choose_k, "{{edges}}": t_edges, "{{edge_effect}}": t_edge_effect,
        "{{profiles}}": t_profiles, "{{fca}}": t_fca, "{{eta}}": t_eta, "{{dynamics}}": t_dynamics, "{{rhythm}}": t_rhythm,
        "{{directed}}": t_directed, "{{synthetic}}": t_synthetic, "{{tr_with}}": lambda: str(trs["mo_with_switches"]),
        "{{tr_dir}}": lambda: str(trs["directed"]), "{{tr_ret}}": lambda: str(trs["returning"]),
        "{{n_moved}}": lambda: str(ee["n_moved"]),
        "{{moved_km}}": lambda: num(ee["neighbors_same_type_kmeans_mean"] * 100, 0) + "%",
        "{{moved_kef}}": lambda: num(ee["neighbors_same_type_kefrin_mean"] * 100, 0) + "%"}


def scalars() -> dict:
    """Числа, которые упоминаются в тексте отчёта, — из результатов, чтобы текст не расходился с outputs/."""
    import yaml as _y
    cfg = _y.safe_load(open(ROOT / "configs" / "pipeline.yaml", encoding="utf-8"))
    K = cfg["typology"]["K"]
    main = "KEFRiN-c (признаки+сеть)" if cfg["typology"]["metric"] == "cosine" else "KEFRiN-e (признаки+сеть)"
    pct = lambda v, d=0: num(v * 100, d) + "%"
    words = {4: "Четыре", 5: "Пять", 6: "Шесть", 7: "Семь", 8: "Восемь", 9: "Девять"}
    v = {"K": str(K), "K1": str(K + 1), "K_word": words.get(K, str(K)), "main": main.split(" ")[0]}
    ck = pd.read_csv(O / "choose_k" / "summary.csv").set_index("K")
    v.update(hennig_K=num(ck.loc[K, "hennig_min"], 2), boot_K=num(ck.loc[K, "boot_ARI"], 2),
             hennig_K1=num(ck.loc[K + 1, "hennig_min"], 2) if K + 1 in ck.index else "—",
             hennig_Km1=num(ck.loc[K - 1, "hennig_min"], 2) if K - 1 in ck.index else "—")
    e = pd.read_csv(O / "interpret" / "external_eta2.csv", index_col=0)
    v.update(eta_cafe=pct(e.loc["share_cafe", "eta2"]), eta_food=pct(e.loc["share_food", "eta2"]),
             eta_cafe_base=pct(e.loc["share_cafe", "eta2_base_only"]), eta_food_base=pct(e.loc["share_food", "eta2_base_only"]),
             eta_mob=pct(e.loc["mobility_index", "eta2"]))
    raw = pd.read_csv(O / "method_comparison" / "icvi_raw.csv", index_col=0)
    km = "k-means (признаки)"
    v.update(sw_main=num(raw.loc[main, "SW"]), sw_km=num(raw.loc[km, "SW"]), mq_main=num(raw.loc[main, "MQ"]),
             mq_km=num(raw.loc[km, "MQ"]), avi_main=num(raw.loc[main, "AVI"]), avi_km=num(raw.loc[km, "AVI"]),
             mq_gain=pct(raw.loc[main, "MQ"] / raw.loc[km, "MQ"] - 1), avi_gain=pct(raw.loc[main, "AVI"] / raw.loc[km, "AVI"] - 1),
             boot_main=num(raw.loc[main, "bootstrap_ARI"], 2), boot_km=num(raw.loc[km, "bootstrap_ARI"], 2))
    v.update(share_moved=pct(ee["share_moved"]), all_km=pct(ee["all_mo_same_type_kmeans"]), all_kef=pct(ee["all_mo_same_type_kefrin"]))
    br = pd.read_csv(O / "edge_effect" / "by_rule.csv", index_col=0)
    v.update(ari_km=num(br.loc["без сети (k-means)", "ARI_with_main"], 2))
    dv = pd.read_csv(O / "dynamics" / "variants.csv", index_col=0)
    ind, mn = dv.loc["независимо по месяцам"], dv.loc[f"эволюционный KEFRiN, α={cfg['dynamics']['alpha']}"]
    a1 = dv.loc[f"эволюционный KEFRiN, α={cfg['dynamics']['alphas'][0]}"]
    v.update(alpha=num(cfg["dynamics"]["alpha"], 2).rstrip("0").rstrip(","), dyn_ind_rate=pct(ind.switch_rate_month, 1),
             dyn_ind_pers=pct(ind.persistent_share_of_all), dyn_main_rate=pct(mn.switch_rate_month, 2),
             dyn_main_never=pct(mn.never_switch, 1), dyn_main_pers=pct(mn.persistent_share_of_all),
             dyn_cut=pct(1 - mn.switch_rate_month / ind.switch_rate_month), dyn_a1_pers=pct(a1.persistent_share_of_all),
             dyn_main_sw=num(mn.SW_median), dyn_ind_sw=num(ind.SW_median), dyn_main_mq=num(mn.MQ_median), dyn_ind_mq=num(ind.MQ_median))
    sy = pd.read_csv(O / "synthetic" / "summary.csv")
    cal = sy[sy["сценарий"] == "калиброванный"].set_index("вариант")
    am, a0 = cal.loc[f"эволюционный, α={cfg['dynamics']['alpha']}"], cal.loc[f"эволюционный, α={cfg['dynamics']['alphas'][0]}"]
    v.update(syn_ind_false=num(cal.loc["независимо", "ложные смены (не мигранты)"], 1),
             syn_main_false=num(am["ложные смены (не мигранты)"], 2), syn_a0_false=num(a0["ложные смены (не мигранты)"], 2),
             syn_main_0=pct(am["мигранты найдены через 0 мес."]), syn_main_2=pct(am["мигранты найдены через 2 мес."]),
             syn_a0_2=pct(a0["мигранты найдены через 2 мес."]),
             syn_false_cut=pct(1 - am["ложные смены (не мигранты)"] / a0["ложные смены (не мигранты)"]))
    mb = pd.read_csv(O / "interpret" / "mobility_by_type.csv", index_col=0).iloc[:, 0].sort_values(ascending=False)
    v["mob_sentence"] = ", ".join(f"{n.lower()} — {num(x, 1)} км" for n, x in mb.items())
    mob = pd.read_csv(O / "interpret" / "mo_types.csv", index_col=0)
    v["n_types"] = ", ".join(f"{n.lower()} — {c}" for n, c in mob.groupby("type_name", sort=False).size().items())
    rk = pd.read_csv(O / "method_comparison" / "ranking.csv", index_col=0)
    zz = pd.read_csv(O / "method_comparison" / "icvi_z.csv", index_col=0)
    ab = pd.read_csv(O / "method_comparison" / "ari_between.csv", index_col=0)
    cn = "CANUS (признаки+сеть)"
    place = {1: "первым", 2: "вторым", 3: "третьим", 4: "четвёртым"}
    v.update(borda_main_word=place.get(int(rk.loc[main, "rank_borda"]), str(int(rk.loc[main, "rank_borda"])) + "-м"),
             ari_main_km=num(ab.loc[main, km], 2), ari_main_e=num(ab.loc[main, "KEFRiN-e (признаки+сеть)"], 2),
             sdbw_km=num(raw.loc[km, "S_Dbw"]), sdbw_main=num(raw.loc[main, "S_Dbw"]),
             zsdbw_km=num(zz.loc[km, "S_Dbw"], 1), zsdbw_main=num(zz.loc[main, "S_Dbw"], 1),
             boot_canus=num(raw.loc[cn, "bootstrap_ARI"], 2), canus_nboot=str(int(raw.loc[cn, "n_boot"])))
    gnn = [g for g in raw.index if "(GNN)" in g]
    ra = O / "method_comparison" / "ranking_all.csv"
    if gnn and ra.exists():
        ra = pd.read_csv(ra, index_col=0)
        short = lambda g: g.replace(" (GNN)", "").split(" (")[0]
        top = ra.index[0]
        gb = min(gnn, key=lambda g: ra.loc[g, "rank_threshold"])
        rows = [[m, int(ra.loc[m, "rank_threshold"]), int(ra.loc[m, "rank_borda"]), num(raw.loc[m, "SW"]), num(raw.loc[m, "MQ"]),
                 num(raw.loc[m, "AVI"]), num(raw.loc[m, "bootstrap_ARI"], 2)] for m in ra.index]
        v["gnn_table"] = md_table(pd.DataFrame(rows, columns=[f"Метод (все {len(ra)})", "место, Алескеров", "место, Борда", "SW ↑", "MQ ↑", "AVI ↑", "бутстрап ↑"]))
        pm = int(ra.loc[main, "rank_threshold"])
        mates = [short(m) for m in ra.index if m != main and int(ra.loc[m, "rank_threshold"]) == pm]
        ctrl = [short(m) for m in ra.index if m not in rk.index]
        place_txt = (f"{v['main']} остаётся на {pm}-м месте" + (f" (делит его с {', '.join(mates)})" if mates else ""))
        v["gnn_sentence"] = (
            f"Пять методов добавлены после выбора как внешний контроль: {', '.join(ctrl)}. Правило выбора основного метода "
            f"задано до их добавления, поэтому рейтинг выбора выше — по восьми исходным методам. В общем рейтинге всех "
            f"{len(ra)} методов (таблица ниже) {place_txt}; места относительны (трети по каждому критерию), и новые участники "
            f"сдвигают пороги. По сути нейросети ведут себя как сетевые методы: у лучшей из них, {short(gb)}, модулярность MQ "
            f"{num(raw.loc[gb, 'MQ'])} против {num(raw.loc[main, 'MQ'])} у {v['main']}, но силуэт {num(raw.loc[gb, 'SW'])} против "
            f"{num(raw.loc[main, 'SW'])} и устойчивость на бутстрапе {num(raw.loc[gb, 'bootstrap_ARI'], 2)} против "
            f"{num(raw.loc[main, 'bootstrap_ARI'], 2)}. Нейросеть группирует МО по тому, с кем они связаны, а не по тому, чем они "
            f"живут, и от подвыборки к подвыборке даёт заметно разные типы. Для экономической типологии это хуже: у типа должен "
            f"быть понятный портрет по признакам, и он не должен зависеть от случайного зерна. KEFRiN задаёт вес сети явно (ξ), "
            f"а его центры читаются как профиль типа. Ward с ограничением связности — другой простой способ учесть сеть — "
            f"неустойчив (бутстрап {num(raw.loc['Ward со связностью (признаки+сеть)', 'bootstrap_ARI'], 2)}).")
    else:
        v["gnn_table"], v["gnn_sentence"] = "", "Графовые нейросети не запускались (нужен PyTorch)."
    af = O / "dynamics" / "affect_alpha.csv"
    if af.exists():
        a = pd.read_csv(af)["alpha"].iloc[1:]
        lm = pd.read_csv(O / "dynamics" / "labels_main.csv", index_col=0).values.ravel()
        la = pd.read_csv(O / "dynamics" / "labels_evolutionary_affect.csv", index_col=0).values.ravel()
        from sklearn.metrics import adjusted_rand_score
        v.update(affect_lo=num(a.min(), 2), affect_hi=num(a.max(), 2), affect_med=num(a.median(), 2),
                 affect_ari=num(adjusted_rand_score(lm, la), 2))
    v.update(sw_best_k=str(int(ck["SW"].idxmax())), ch_best_k=str(int(ck["CH"].idxmax())))
    vs = O / "validation" / "summary.json"
    if vs.exists():
        vj = json.load(open(vs, encoding="utf-8"))
        ho = pd.read_csv(O / "validation" / "held_out.csv")
        v.update(ho_wage=pct(vj["held_out_wage_eta2"]), ho_wage_main=pct(vj["held_out_wage_eta2_main"]),
                 ho_emp=pct(vj["held_out_emp_eta2_mean"]), ho_n=str(len(ho)),
                 tr_sig=str(vj["transitions_p05"]), tr_exp=num(vj["transitions_p05_expected"], 1),
                 tr_binom="10" + str(int(__import__("math").floor(__import__("math").log10(vj["transitions_binom_p"])))).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")),
                 tr_ratio=num(vj["shift_median_movers"] / vj["shift_median_stable"], 1))
    cpf = O / "method_comparison" / "ranking_copeland.csv"
    if cpf.exists():
        cp = pd.read_csv(cpf, index_col=0, header=[0, 1])["выбор (8 методов)"].dropna()
        v.update(cop_main=str(int(cp.loc[main, "rank_copeland"])),
                 cop_first=cp["rank_copeland"].idxmin().split(" (")[0])
    rf = O / "method_comparison" / "external_railway.csv"
    if rf.exists():
        rl = pd.read_csv(rf, index_col=0)
        v.update(rail_main=str(int(rl.loc[main, "rank"])), rail_km=str(int(rl.loc[km, "rank"])),
                 rail_z_main=num(rl.loc[main, "mean_z"], 0), rail_z_km=num(rl.loc[km, "mean_z"], 0), rail_n="1 262")
    mb = O / "method_comparison" / "ranking_mq_basic.csv"
    if mb.exists():
        mb = pd.read_csv(mb, index_col=0)
        v.update(mqb_rank=str(int(mb.loc[main, "rank_threshold"])), mqb_borda=str(int(mb.loc[main, "rank_borda"])))
    if "snf" in br.index:
        es = pd.read_csv(O / "edges" / "summary.csv", index_col=0)
        v.update(snf_region=pct(es.loc["snf", "within_region"]), snf_sw=num(br.loc["snf", "SW"]),
                 snf_ari=num(br.loc["snf", "ARI_with_main"], 2))
    rv = pd.read_csv(O / "method_comparison" / "ranking_variants.csv", index_col=0)
    v["main_firsts"] = str(int(rv.loc[main, "первых мест"]))
    ds = json.load(open(O / "interpret" / "divergence_summary.json", encoding="utf-8"))
    v.update(gap_top=ds["top_type"].lower(), gap_bot=ds["bottom_type"].lower(),
             gap_spread23=num(ds["spread_2023"], 0), gap_spread24=num(ds["spread_2024"], 0),
             gap_sigma23=num(ds["sigma_2023"], 3), gap_sigma24=num(ds["sigma_2024"], 3),
             gap_eta23=pct(ds["eta2_2023"]), gap_eta24=pct(ds["eta2_2024"]),
             gap_ci=f"от +{num(ds['spread_change_ci95'][0], 1)} до +{num(ds['spread_change_ci95'][1], 1)}")
    return v


try:
    SC = scalars()
except (FileNotFoundError, KeyError) as e:
    print("числа для текста посчитаны не все:", e)
    SC = {}
for k, val in SC.items():
    subs["{{" + k + "}}"] = (lambda x: (lambda: x))(val)
for k, f in subs.items():
    if k in src:
        try:
            src = src.replace(k, f())
        except FileNotFoundError as e:
            print("нет данных для", k, e)
import re as _re
left = sorted(set(_re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", src)))
if left:
    print("НЕ ПОДСТАВЛЕНЫ:", left)
# основной текст и приложения — отдельными файлами; PDF собирается из обоих
cut = src.find("\n## Приложение А")
main_md, app_md = (src[:cut], src[cut:]) if cut > 0 else (src, "")
if app_md:
    main_md += ("\n\n*Приложения А–Д (формулы индексов, детали сравнения методов, дополнительные таблицы) — "
                "в `report/uklad_appendix.md`.*\n")
    (R / "uklad_appendix.md").write_text("# Уклад: приложения к методологическому отчёту\n" + app_md, encoding="utf-8")
(R / "uklad_methodology.md").write_text(main_md, encoding="utf-8")

body = MarkdownIt("commonmark", {"html": False}).enable("table").render(src)
css = """body{font:11pt/1.5 'Segoe UI',system-ui,sans-serif;color:#0b0b0b;max-width:900px;margin:0 auto;padding:24px}
h1{font-size:22pt;line-height:1.15}h2{font-size:15pt;margin-top:22px;border-bottom:1px solid #e1e0d9;padding-bottom:3px}
h3{font-size:12pt}table{border-collapse:collapse;font-size:8.5pt;margin:8px 0;width:100%}
th,td{border-bottom:1px solid #e1e0d9;padding:3px 5px;text-align:left;vertical-align:top}th{color:#52514e}
img{max-width:100%}code,pre{font-size:9pt;background:#f2f1ed}pre{padding:8px}em{color:#52514e}
@page{size:A4;margin:14mm}h2{break-after:avoid}table,img{break-inside:avoid}"""
html = f"<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Методологический отчёт</title><style>{css}</style></head><body>{body}</body></html>"
(R / "uklad_methodology.html").write_text(html, encoding="utf-8")

browser = next((p for p in [shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
                            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"] if p and Path(p).exists()), None)
if browser:
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={R / 'uklad_methodology.pdf'}", (R / "uklad_methodology.html").as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("report/uklad_methodology.pdf")
else:
    print("Chrome/Edge не найден: PDF не собран, есть report/uklad_methodology.html")
print("report/uklad_methodology.md")
