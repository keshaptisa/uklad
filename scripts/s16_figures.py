"""Шаг 9. Рисунки для отчёта: report/figures/*.png.

Правила оформления: один акцентный цвет на сером фоне вместо семи категориальных цветов (7 типов на карте не различимы
для читателей с нарушением цветового зрения), подписи вместо легенд, тонкие линии, одна ось Y.
Каждый рисунок строится, только если есть его входные файлы — шаги пайплайна можно запускать по отдельности.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402

cfg = load_config()
O = ROOT / cfg["paths"]["outputs"]
FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
NAMES = yaml.safe_load(open(ROOT / "configs" / "typology.yaml", encoding="utf-8"))["names"]

ACCENT, ACCENT_DARK, BASE = "#2a78d6", "#184f95", "#e1e0d9"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
RED = "#e34948"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK,
})
ALBERS = "+proj=aea +lat_1=52 +lat_2=64 +lat_0=0 +lon_0=100 +datum=WGS84 +units=m"


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("рисунок", name)


def load_geo():
    g = gpd.read_file(ROOT / "site_src" / "data" / "geo.json")
    g["territory_id"] = [f["id"] for f in json.load(open(ROOT / "site_src" / "data" / "geo.json"))["features"]]
    return g.set_crs(4326).to_crs(ALBERS)


def fig_type_maps():
    mt = pd.read_csv(O / "interpret" / "mo_types.csv", index_col=0)
    # столбец не называем «type»: у GeoDataFrame это встроенный атрибут (тип геометрии)
    g = load_geo().merge(mt[["type"]].rename(columns={"type": "tp"}), left_on="territory_id", right_index=True)
    K = int(mt.type.max()) + 1
    fig, axes = plt.subplots(2, 4, figsize=(13, 5.2))
    for k, ax in enumerate(axes.flat):
        ax.set_axis_off()
        if k >= K:
            ax.text(0.02, 0.5, "Каждая карта — один тип:\nего МО выделены цветом,\nостальные — серым.\n\n"
                    "Москва и Петербург —\nсотни мелких МО, на карте\nстраны почти не видны;\nсм. лендинг.",
                    color=INK2, fontsize=8.5, va="center", transform=ax.transAxes)
            continue
        m = g["tp"] == k
        g[~m].plot(ax=ax, color=BASE, linewidth=0)
        g[m].plot(ax=ax, color=ACCENT, linewidth=0)
        import textwrap
        ax.set_title(textwrap.fill(f"{NAMES[k]} · {int(m.sum())} МО", 30), fontsize=9, loc="left", color=INK)
    fig.suptitle(f"Типы локальных экономик (KEFRiN, K = {K})", x=0.01, ha="left", fontweight="bold", color=INK)
    save(fig, "fig1_type_maps")


def fig_choose_k():
    s = pd.read_csv(O / "choose_k" / "summary.csv")
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(s.K, s.boot_ARI, color=ACCENT, lw=2, marker="o", ms=5, label="устойчивость разбиения (бутстрап ARI)")
    ax.plot(s.K, s.hennig_min, color=INK2, lw=2, marker="o", ms=5, label="самый неустойчивый тип (Жаккар Хеннига)")
    ax.axhline(0.75, color=MUTED, lw=1, ls="--")
    ax.text(s.K.max(), 0.755, "порог устойчивости 0,75", color=MUTED, ha="right", va="bottom", fontsize=8)
    k7 = s[s.K == cfg["typology"]["K"]].iloc[0]
    ax.annotate(f"K = {int(k7.K)}: все типы ещё устойчивы", (k7.K, k7.hennig_min), xytext=(k7.K - 0.2, 0.62),
                ha="right", arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8), color=INK, fontsize=8.5)
    ax.set_xlabel("число типов K")
    ax.set_ylim(0.45, 1.02)
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    ax.set_title("Выбор числа типов: наибольшее K, при котором устойчив каждый тип")
    save(fig, "fig2_choose_k")


def fig_methods():
    z = pd.read_csv(O / "method_comparison" / "icvi_z.csv", index_col=0)
    r = pd.read_csv(O / "method_comparison" / "ranking.csv", index_col=0)
    crit = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]
    order = r.index.tolist()
    fig, axes = plt.subplots(1, len(crit), figsize=(13, 3.3), sharey=True)
    for ax, c in zip(axes, crit):
        v = z.loc[order, c]
        best = v.idxmax()
        ax.barh(range(len(order)), v.values, color=[ACCENT if n == best else BASE for n in order], height=0.6)
        ax.set_title(c + (" ↓" if c in ("S_Dbw", "AVU") else " ↑"), fontsize=9)
        ax.axvline(0, color="#c3c2b7", lw=0.8)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels([f"{i + 1}. {n}" for i, n in enumerate(order)], color=INK)
    axes[0].invert_yaxis()
    fig.suptitle(f"Методы при K = {cfg['typology']['K']}: z-оценка индекса против случайной перестановки меток (больше — лучше; синим — лучший)",
                 x=0.01, ha="left", fontweight="bold", color=INK, fontsize=10)
    fig.text(0.01, -0.04, "Порядок — рейтинг порогового агрегирования Алескерова по шести ICVI и бутстрап-устойчивости. "
             "Для S_Dbw и AVU знак обращён.", color=INK2, fontsize=8)
    save(fig, "fig3_methods")


def fig_profiles():
    dev = pd.read_csv(O / "interpret" / "mirkin_dev.csv", index_col=0)
    lab = {"spend": "траты на жителя", "share_food": "доля продовольствия", "share_cafe": "доля общепита",
           "share_market": "доля маркетплейсов", "share_transport": "доля транспорта", "share_health": "доля здоровья",
           "wage": "зарплата", "population": "население", "urban_share": "доля горожан", "market_access": "доступность рынков",
           "emp_agro": "занятость: сельское хоз.", "emp_mining": "занятость: добыча",
           "emp_industry": "занятость: промышленность", "emp_transport": "занятость: транспорт", "emp_market_services": "занятость: рыночные услуги",
           "emp_public": "занятость: бюджетный сектор"}
    cols = [c for c in lab if c in dev.columns]
    D = dev[cols].clip(-100, 100)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("div", ["#184f95", "#86b6ef", "#f0efec", "#f0a3a2", "#b42a2a"])
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.imshow(D.values, cmap=cmap, vmin=-100, vmax=100, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([lab[c] for c in cols], rotation=35, ha="right")
    ax.set_yticks(range(len(D)))
    ax.set_yticklabels(D.index, color=INK)
    ax.grid(False)
    for i in range(D.shape[0]):
        for j in range(D.shape[1]):
            v = dev[cols].values[i, j]
            ax.text(j, i, f"{v:+.0f}" if abs(v) < 1000 else f"×{v / 100 + 1:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(v) > 65 else INK)
    ax.set_title("Профили типов по Миркину: отклонение среднего типа от среднего по стране, %")
    save(fig, "fig4_profiles")


def fig_dynamics():
    p = O / "dynamics" / "labels_main.csv"
    if not p.exists():
        return
    L = pd.read_csv(p, index_col=0)
    months = L.columns.tolist()
    sw = (L.values[:, 1:] != L.values[:, :-1]).sum(0)
    fig, ax = plt.subplots(figsize=(7, 2.6))
    ax.bar(range(1, len(months)), sw, color=ACCENT, width=0.7)
    ax.set_xticks(range(1, len(months), 2))
    ax.set_xticklabels(months[1::2], rotation=45, ha="right", fontsize=7.5)
    ax.set_ylabel("МО сменили тип")
    ax.set_title("Сколько МО меняют тип за месяц (эволюционный KEFRiN)")
    save(fig, "fig5_switches")


def fig_rhythm():
    p = O / "rhythm" / "profiles.csv"
    if not p.exists():
        return
    prof = pd.read_csv(p, header=[0, 1], index_col=0)
    t = pd.read_csv(O / "rhythm" / "types.csv")
    names = {0: "летний пик", 1: "зимний пик", 2: "арктический июль", 3: "северо-восточный август"}
    fig, axes = plt.subplots(1, len(t), figsize=(12, 2.8), sharey=True)
    m = np.arange(1, 13)
    for ax, (_, r) in zip(axes, t.iterrows()):
        k = int(r.rhythm_type)
        ax.plot(m, prof.loc[str(k) if str(k) in prof.index else k, "cafe"].values * 100, color=MUTED, lw=1.5, label="общепит")
        ax.plot(m, prof.loc[str(k) if str(k) in prof.index else k, "total"].values * 100, color=ACCENT, lw=2, label="все траты")
        ax.axhline(0, color="#c3c2b7", lw=0.8)
        ax.set_xticks([1, 4, 7, 10])
        ax.set_xticklabels(["янв", "апр", "июл", "окт"])
        ax.set_title(f"{names.get(k, k)} · {int(r.n)} МО", fontsize=9)
    axes[0].set_ylabel("% к общероссийскому месяцу")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Линза ритма: четыре типа собственного сезонного ритма (повторился в 2023 и 2024 гг.)", x=0.01, y=1.06,
                 ha="left", fontweight="bold", color=INK, fontsize=10)
    save(fig, "fig6_rhythm")


for f in [fig_type_maps, fig_choose_k, fig_methods, fig_profiles, fig_dynamics, fig_rhythm]:
    try:
        f()
    except FileNotFoundError as e:
        print("пропуск", f.__name__, e)
