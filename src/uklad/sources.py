"""Сборка панели: расходы СберИндекса × справочник МО × Росстат × доступность рынков.

Выход (data/processed):
- spend.parquet   — длинная таблица territory_id, month, category, value (руб. на жителя в месяц), только МО с полной историей;
- mo.parquet      — по одной строке на МО: название, регион, тип, координаты, ОКТМО, контекст Росстата, доступность рынков.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import ROOT, load_config


def _oktmo8(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace("-", "", regex=False).str[:8]


def load_spend(cfg: dict) -> pd.DataFrame:
    raw = ROOT / cfg["paths"]["raw"]
    c = pd.read_parquet(raw / "hackathonlicence" / "consumption.parquet")
    c = c.rename(columns={"date": "month"})
    c["category"] = c["category"].map(cfg["data"]["categories"])
    lo, hi = cfg["data"]["months"]
    c = c[(c.month >= lo) & (c.month <= hi)]
    n_months = c.month.nunique()
    n_cells = c.groupby("territory_id").size()
    full = n_cells[n_cells == n_months * len(cfg["data"]["categories"])].index
    c = c[c.territory_id.isin(full)].copy()
    c["territory_id"] = c["territory_id"].astype(int)
    return c[["territory_id", "month", "category", "value"]].sort_values(["territory_id", "category", "month"])


def load_dict(cfg: dict) -> pd.DataFrame:
    raw = ROOT / cfg["paths"]["raw"]
    d = pd.read_excel(raw / "dict" / "t_dict_municipal_districts.xlsx", dtype={"oktmo": str})
    # действующая запись: самая поздняя по year_to
    d = d.sort_values(["territory_id", "year_to"]).drop_duplicates("territory_id", keep="last")
    d = d.rename(columns={
        "municipal_district_name_short": "name",
        "municipal_district_name": "name_full",
        "municipal_district_type": "mo_type",
        "municipal_district_status": "mo_status",
        "municipal_district_center_lat": "lat",
        "municipal_district_center_lon": "lon",
    })
    d["oktmo8"] = _oktmo8(d["oktmo"])
    return d[["territory_id", "name", "name_full", "mo_type", "mo_status", "region_code", "region_name",
              "lat", "lon", "oktmo8"]].set_index("territory_id")


def _rosstat(cfg: dict, code: str) -> pd.DataFrame:
    raw = ROOT / cfg["paths"]["raw"] / "rosstat"
    frames = []
    for y in (cfg["data"]["rosstat_year"] - 1, cfg["data"]["rosstat_year"]):
        f = pd.read_csv(raw / f"{code}_{y}.csv", sep=";", dtype=str)
        f = f[f.mun_level == "Муниципальное образование верхнего уровня"]
        frames.append(f)
    f = pd.concat(frames)
    f["value"] = pd.to_numeric(f["indicator_value"], errors="coerce")
    f["year"] = f["year"].astype(int)
    return f.dropna(subset=["value"])


def _latest(f: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Значение за самый поздний доступный год для каждого ключа."""
    return f.sort_values("year").drop_duplicates(keys, keep="last")


def load_rosstat(cfg: dict, oktmo_set: set[str]) -> pd.DataFrame:
    period = cfg["data"]["rosstat_period"]
    out = {}

    # население на 1 января: всё и городское
    p = _rosstat(cfg, "Y48112027")
    p = _latest(p, ["oktmo", "mest"])
    pop = p.pivot_table(index="oktmo", columns="mest", values="value", aggfunc="first")
    out["population"] = pop.get("Все население")
    out["urban_share"] = (pop.get("Городское население") / pop.get("Все население")).clip(0, 1)

    # зарплата и численность работников по ОКВЭД2 за год
    letter = lambda s: s.str.extract(r"Раздел (\S)")[0]
    w = _rosstat(cfg, "Y48423007")
    w = w[w.indicator_period == period]
    w = _latest(w, ["oktmo", "okved2"])
    out["wage"] = w[w.okved2.str.startswith("Всего")].set_index("oktmo")["value"]

    e = _rosstat(cfg, "Y48423005")
    e = e[e.indicator_period == period]
    e = _latest(e, ["oktmo", "okved2"])
    tot = e[e.okved2.str.startswith("Всего")].set_index("oktmo")["value"]
    out["employees"] = tot
    e = e[~e.okved2.str.startswith("Всего")].copy()
    e["sec"] = letter(e["okved2"])
    for g, secs in cfg["okved_groups"].items():
        s = e[e.sec.isin(secs)].groupby("oktmo")["value"].sum()
        out[f"emp_{g}"] = (s / tot).clip(0, 1)

    r = pd.DataFrame(out)
    r.index = r.index.astype(str).str.zfill(8)
    return r[r.index.isin(oktmo_set)]


def build(cfg: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = cfg or load_config()
    spend = load_spend(cfg)
    ids = spend.territory_id.unique()
    mo = load_dict(cfg).loc[ids]

    ros = load_rosstat(cfg, set(mo.oktmo8))
    mo = mo.join(ros, on="oktmo8")
    # доли отраслей, которых нет в разрезе (засекречено или нет предприятий), = 0, если известна общая численность
    emp_cols = [c for c in mo.columns if c.startswith("emp_")]
    mo.loc[mo.employees.notna(), emp_cols] = mo.loc[mo.employees.notna(), emp_cols].fillna(0)

    # Росстат считает работников по месту работы. Во внутригородских территориях Москвы и Петербурга
    # («спальные» районы: 2–4 тыс. рабочих мест на 70 тыс. жителей) это структура нескольких местных предприятий,
    # а не занятость жителей, которые работают по всему городу. Таким МО присваиваем общегородские значения:
    # доли отраслей и зарплату, взвешенную по числу работников, по всем территориям города.
    inner = mo.mo_type.str.contains("внутригородская территория города федерального значения", na=False)
    mo["context_citywide"] = inner.astype(int)
    for reg, grp in mo[inner].groupby("region_name"):
        g = mo[(mo.region_name == reg) & inner & mo.employees.notna()]
        wsum = g.employees.sum()
        mo.loc[grp.index, "wage"] = (g.wage * g.employees).sum() / wsum
        for c in emp_cols:
            mo.loc[grp.index, c] = (g[c] * g.employees).sum() / wsum

    # нет строки «Городское население» — в МО нет городов
    mo.loc[mo.population.notna() & mo.urban_share.isna(), "urban_share"] = 0.0

    # координаты центра: из справочника, иначе — внутренняя точка полигона
    import geopandas as gpd
    g = gpd.read_file(ROOT / cfg["paths"]["raw"] / "dict" / "t_dict_municipal_districts_poly.gpkg")
    g["territory_id"] = pd.to_numeric(g["territory_id"], errors="coerce")
    g = g.dropna(subset=["territory_id"]).astype({"territory_id": int})
    g = g.sort_values("year_to").drop_duplicates("territory_id", keep="last").set_index("territory_id")
    pt = g.geometry.representative_point()
    miss = mo.lat.isna() & mo.index.isin(g.index)
    mo.loc[miss, "lat"] = pt.y.reindex(mo.index[miss]).values
    mo.loc[miss, "lon"] = pt.x.reindex(mo.index[miss]).values

    ma = pd.read_parquet(ROOT / cfg["paths"]["raw"] / "hackathonlicence" / "market_access.parquet")
    mo = mo.join(ma.set_index("territory_id")["market_access"])
    mo["is_city"] = mo.mo_type.str.contains("городской округ|внутригородск", case=False, na=False).astype(int)
    mo.index.name = "territory_id"

    outdir = ROOT / cfg["paths"]["processed"]
    outdir.mkdir(parents=True, exist_ok=True)
    spend.to_parquet(outdir / "spend.parquet", index=False)
    mo.to_parquet(outdir / "mo.parquet")
    return spend, mo
