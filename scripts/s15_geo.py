"""Шаг 8а. Упрощённые границы МО для карты лендинга: site_src/data/geo.json.

Полигоны справочника СберИндекса (2660 шт., 70 МБ) упрощаются по Дугласу–Пекеру, координаты округляются,
внешние кольца ориентируются по часовой стрелке (так их ждёт d3-geo). Остаются только МО панели.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping
from shapely.geometry.polygon import orient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import ROOT, load_config  # noqa: E402

cfg = load_config()
gc = cfg["site"]
ids = set(pd.read_parquet(ROOT / cfg["paths"]["processed"] / "mo.parquet").index)
g = gpd.read_file(ROOT / cfg["paths"]["raw"] / "dict" / "t_dict_municipal_districts_poly.gpkg")
g["territory_id"] = pd.to_numeric(g["territory_id"], errors="coerce")
g = g.dropna(subset=["territory_id"]).astype({"territory_id": int})
g = g.sort_values("year_to").drop_duplicates("territory_id", keep="last")
g = g[g.territory_id.isin(ids)]
# в крупных городах МО маленькие: упрощаем мягче там, где полигон мал
area = g.geometry.area
tol = np.where(area < gc["small_area"], gc["tol_small"], gc["tol"])
geoms = [geom.simplify(t, preserve_topology=True) for geom, t in zip(g.geometry, tol)]


def orient_cw(geom):
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    return type(geom)([orient(p, sign=-1.0) for p in geom.geoms])


def rnd(obj, nd):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, nd) for v in obj]
        return [rnd(o, nd) for o in obj]
    return obj


feats = []
for tid, geom in zip(g.territory_id, geoms):
    if geom.is_empty:
        continue
    gm = mapping(orient_cw(geom))
    feats.append({"type": "Feature", "id": int(tid), "properties": {},
                  "geometry": {"type": gm["type"], "coordinates": rnd(gm["coordinates"], gc["decimals"])}})
outdir = ROOT / "site_src" / "data"
outdir.mkdir(parents=True, exist_ok=True)
s = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"))
(outdir / "geo.json").write_text(s, encoding="utf-8")
print(f"МО на карте: {len(feats)} из {len(ids)}, размер {len(s) / 1e6:.1f} МБ")
