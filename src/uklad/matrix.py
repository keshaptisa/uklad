"""Единая сборка атрибутированной сети для всех шагов: МО, атрибуты Y, граф A, сырые показатели для интерпретации."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import ROOT, load_config
from . import attributes as F


@dataclass
class Design:
    ids: np.ndarray            # territory_id в порядке строк
    mo: pd.DataFrame           # справочник + контекст (сырые единицы)
    Y: pd.DataFrame            # стандартизованные атрибуты
    A: sp.csr_matrix           # граф сходства потребления
    monthly: pd.DataFrame      # помесячные признаки потребления (level, clr_*, engel)
    raw: pd.DataFrame          # показатели в исходных единицах для интерпретации


def load(cfg: dict | None = None) -> Design:
    cfg = cfg or load_config()
    P = ROOT / cfg["paths"]["processed"]
    spend = pd.read_parquet(P / "spend.parquet")
    mo = pd.read_parquet(P / "mo.parquet")
    mf = F.monthly_features(spend)
    ids = mf.index.get_level_values(0).unique().values
    mo = mo.loc[ids]
    ctx = F.context(mo)
    cons = mf.groupby(level=0).mean().loc[ids]
    X = pd.concat([ctx, cons], axis=1)
    Y = F.standardize(X[cfg["typology"]["attributes"]])
    A = sp.load_npz(P / "graphs" / f"static_{cfg['typology']['graph']}.npz").tocsr()

    w = F.spend_cube(spend)
    sh = F.shares(w).groupby(level=0).mean().loc[ids]
    raw = pd.DataFrame({
        "spend": w["total"].groupby(level=0).mean().loc[ids],
        **{f"share_{p}": sh[p] * 100 for p in F.PARTS},
        "wage": mo.wage, "population": mo.population, "urban_share": mo.urban_share * 100,
        "market_access": mo.market_access,
        **{c: mo[c] * 100 for c in ["emp_agro", "emp_mining", "emp_industry", "emp_transport", "emp_market_services", "emp_public"]},
    })
    return Design(ids, mo, Y, A, mf, raw)
