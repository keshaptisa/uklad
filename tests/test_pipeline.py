"""Сквозная проверка конвейера на синтетической панели с известной истиной (без скачивания данных).

Панель: 3 типа × 40 МО × 12 месяцев. Атрибуты узла — постоянная «экономическая база» типа; ряды трат — свой
сезонный профиль у каждого типа. В 6-м месяце 4 МО по-настоящему переходят в другой тип.
Конвейер — те же функции, что и в scripts/: DTW-kNN граф → KEFRiN → ICVI и рейтинг → помесячные сети →
эволюционное отслеживание (постоянная α и AFFECT) → устойчивые переходы.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ARI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad import network as G  # noqa: E402
from uklad import partition as C  # noqa: E402
from uklad import tracking as TM  # noqa: E402
from uklad.aggregate import threshold_aggregation  # noqa: E402
from uklad.quality import icvi, icvi_z  # noqa: E402

K, n, T, t_switch = 3, 40, 12, 6
MOVERS = np.array([0, 1, 40, 41])  # переходят в следующий тип


def panel(seed=0):
    rng = np.random.default_rng(seed)
    y0 = np.repeat(np.arange(K), n)
    yt = np.tile(y0, (T, 1))
    yt[t_switch:, MOVERS] = (y0[MOVERS] + 1) % K
    base = 2.5 * np.eye(K, 5)
    season = np.stack([np.sin(2 * np.pi * (np.arange(T) + 3 * k) / T) for k in range(K)])
    Y = [base[yt[t]] + rng.normal(scale=0.4, size=(K * n, 5)) for t in range(T)]
    S = np.stack([season[yt[:, i], np.arange(T)] + rng.normal(scale=0.15, size=T) for i in range(K * n)])
    return y0, yt, Y, S


def test_static_pipeline_recovers_types_and_ranks_joint_method():
    y0, _, Y, S = panel()
    Ystat = np.mean(Y[:t_switch], axis=0)
    A = G.knn_graph(-G.dtw_dist(S[:, :t_switch, None], window=1), 8)
    lab = {"k-means": C.kmeans(Ystat, K, seed=0),
           "KEFRiN": C.kefrin(Ystat, C.modularity_rows(A), K, seed=0, n_init=5, metric="cosine"),
           "Leiden": C.leiden_k(A, K)}
    assert ARI(y0, lab["KEFRiN"]) > 0.9
    raw = {m: icvi(Ystat, A, y) for m, y in lab.items()}
    assert set(raw["KEFRiN"]) >= {"SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"}
    Z = pd.DataFrame({m: icvi_z(Ystat, A, y, n_perm=10) for m, y in lab.items()}).T
    rank = threshold_aggregation(Z[["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ"]])
    assert len(rank) == 3 and rank["rank_threshold"].min() == 1


def test_dynamic_pipeline_finds_true_switches():
    y0, yt, Y, S = panel()
    As = [G.knn_graph(G.cosine_sim(np.c_[Y[t], S[:, max(0, t - 2):t + 1].mean(1)]), 8) for t in range(T)]
    y_init = C.kefrin(Y[0], C.modularity_rows(As[0]), K, seed=0, n_init=5)
    rho, xi = C.kefrin_weights(Y[0], C.modularity_rows(As[0]))
    L = TM.evolutionary_kefrin(Y, As, K, 0.5, y_init, rho, xi, seed=0)
    La, alphas = TM.affect_kefrin(Y, As, K, y_init, rho, xi, seed=0)
    assert L.shape == La.shape == (T, K * n)
    assert np.all((alphas[1:] >= 0) & (alphas[1:] <= 0.95))
    # постоянная α = 0,5 (основная модель): все настоящие переходы найдены, ложных почти нет
    assert ARI(yt[-1], L[-1]) > 0.85
    found = set(TM.persistent_switches(L, min_run=3)["i"])
    assert set(MOVERS) <= found
    assert len(found - set(MOVERS)) <= 2
    # AFFECT на спокойных данных копит память (α растёт), поэтому переход замечает позже, но тоже замечает:
    # к концу панели перешедшие МО уже в новом типе. Это и причина, почему основной оставлена постоянная α
    assert alphas[-1] > alphas[1]
    assert ARI(yt[-1], La[-1]) > 0.85
    first_new = [int(np.argmax(La[:, i] != La[0, i])) for i in MOVERS]
    first_new_L = [int(np.argmax(L[:, i] != L[0, i])) for i in MOVERS]
    assert min(first_new) >= min(first_new_L)
