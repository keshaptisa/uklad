"""Глубокие графовые методы кластеризации атрибутированной сети — контрольная группа к KEFRiN.

Собственные компактные реализации на PyTorch по статьям (полный граф 2 016 МО помещается в память плотно):
- GAE + k-means (Kipf & Welling 2016): двухслойный GCN-кодировщик, декодер ⟨z_i, z_j⟩ восстанавливает рёбра,
  затем k-means на эмбеддингах;
- DAEGC (Wang et al., IJCAI 2019): тот же автоэнкодер, но кодировщик — графовое внимание (GAT), и после
  предобучения — самообучение: мягкие метки Стьюдента q, целевое распределение p ∝ q²/f, штраф KL(p‖q);
- DMoN (Tsitsulin et al., JMLR 2023): GCN выдаёт мягкое назначение C = softmax(·), минимизируется
  −Tr(Cᵀ B C)/2m (спектральная модулярность) + штраф на коллапс √K/n‖Σ_i C_i‖ − 1.
Все три видят и признаки, и сеть — как KEFRiN, но через нейросеть.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from sklearn.cluster import KMeans


def _torch():
    import torch
    torch.set_num_threads(4)
    return torch


def _prep(Y, A):
    torch = _torch()
    A = sp.csr_matrix(A, dtype=np.float32)
    A = ((A + A.T) / 2).toarray()
    np.fill_diagonal(A, 0)
    A = A.astype(np.float32)
    At = A + np.eye(len(A), dtype=np.float32)
    d = At.sum(1) ** -0.5
    An = (d[:, None] * At * d[None, :]).astype(np.float32)
    X = np.asarray(Y, np.float32)
    return torch.tensor(X), torch.tensor(A), torch.tensor(An), torch.tensor((A > 0).astype(np.float32))


class _GCN:
    def __init__(self, torch, dims, gen):
        self.W = [torch.nn.Parameter(torch.randn(a, b, generator=gen) * (2 / (a + b)) ** 0.5)
                  for a, b in zip(dims[:-1], dims[1:])]

    def __call__(self, X, An):
        for i, W in enumerate(self.W):
            X = An @ (X @ W)
            if i < len(self.W) - 1:
                X = X.relu()
        return X


class _GAT:
    """Одноголовое графовое внимание по рёбрам (с петлями), как в DAEGC."""

    def __init__(self, torch, dims, gen):
        self.t = torch
        self.W = [torch.nn.Parameter(torch.randn(a, b, generator=gen) * (2 / (a + b)) ** 0.5)
                  for a, b in zip(dims[:-1], dims[1:])]
        self.a = [torch.nn.Parameter(torch.randn(2, b, generator=gen) * 0.1) for b in dims[1:]]

    def __call__(self, X, mask):
        t = self.t
        for i, (W, a) in enumerate(zip(self.W, self.a)):
            H = X @ W
            e = t.nn.functional.leaky_relu((H @ a[0])[:, None] + (H @ a[1])[None, :], 0.2)
            e = e.masked_fill(mask == 0, -1e9)
            X = t.softmax(e, 1) @ H
            if i < len(self.W) - 1:
                X = t.nn.functional.elu(X)
        return X

    @property
    def params(self):
        return self.W + self.a


def _recon_loss(torch, Z, Ab):
    Z = torch.nn.functional.normalize(Z, dim=1)
    logits = Z @ Z.T * 5
    pos = Ab.sum()
    w = (Ab.numel() - pos) / pos
    return torch.nn.functional.binary_cross_entropy_with_logits(logits, Ab, pos_weight=w)


def gae_kmeans(Y, A, K, seed=0, hidden=32, dim=16, epochs=200, lr=0.01, **_):
    torch = _torch()
    gen = torch.Generator().manual_seed(seed)
    X, _, An, Ab = _prep(Y, A)
    enc = _GCN(torch, [X.shape[1], hidden, dim], gen)
    opt = torch.optim.Adam(enc.W, lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        _recon_loss(torch, enc(X, An), Ab).backward()
        opt.step()
    Z = torch.nn.functional.normalize(enc(X, An), dim=1).detach().numpy()
    return KMeans(K, n_init=20, random_state=seed).fit_predict(Z)


def daegc(Y, A, K, seed=0, hidden=32, dim=16, pre_epochs=150, epochs=100, lr=0.005, gamma=10.0, **_):
    torch = _torch()
    gen = torch.Generator().manual_seed(seed)
    X, _, _, Ab = _prep(Y, A)
    mask = Ab + torch.eye(len(Ab))
    enc = _GAT(torch, [X.shape[1], hidden, dim], gen)
    opt = torch.optim.Adam(enc.params, lr=lr)
    for _ in range(pre_epochs):
        opt.zero_grad()
        _recon_loss(torch, enc(X, mask), Ab).backward()
        opt.step()
    Z0 = torch.nn.functional.normalize(enc(X, mask), dim=1).detach().numpy()
    mu = torch.nn.Parameter(torch.tensor(KMeans(K, n_init=20, random_state=seed).fit(Z0).cluster_centers_,
                                         dtype=torch.float32))
    opt = torch.optim.Adam(enc.params + [mu], lr=lr)

    def soft(Z):
        q = 1.0 / (1.0 + torch.cdist(Z, mu) ** 2)
        return q / q.sum(1, keepdim=True)

    for ep in range(epochs):
        Z = torch.nn.functional.normalize(enc(X, mask), dim=1)
        q = soft(Z)
        if ep % 5 == 0:  # цель обновляем реже, как в статье
            p = (q ** 2 / q.sum(0)).detach()
            p = p / p.sum(1, keepdim=True)
        loss = gamma * torch.nn.functional.kl_div(q.log(), p, reduction="batchmean") + _recon_loss(torch, Z, Ab)
        opt.zero_grad()
        loss.backward()
        opt.step()
    return soft(torch.nn.functional.normalize(enc(X, mask), dim=1)).argmax(1).numpy()


def dmon(Y, A, K, seed=0, hidden=64, epochs=400, lr=0.01, collapse=1.0, n_init=3, **_):
    """Лучший по модулярности из n_init запусков; пустые кластеры невозможны благодаря штрафу на коллапс."""
    torch = _torch()
    X, Aw, An, _ = _prep(Y, A)
    k = Aw.sum(1)
    m2 = k.sum()
    n = len(X)
    best, best_q = None, -np.inf
    for r in range(n_init):
        gen = torch.Generator().manual_seed(seed * 101 + r)
        enc = _GCN(torch, [X.shape[1], hidden, K], gen)
        opt = torch.optim.Adam(enc.W, lr=lr)
        for _ in range(epochs):
            Cs = torch.softmax(enc(X, An), 1)
            mod = (torch.trace(Cs.T @ Aw @ Cs) - ((Cs.T @ k) ** 2).sum() / m2) / m2
            col = torch.linalg.norm(Cs.sum(0)) / n * K ** 0.5 - 1
            loss = -mod + collapse * col
            opt.zero_grad()
            loss.backward()
            opt.step()
        if mod.item() > best_q:
            best_q, best = mod.item(), Cs.argmax(1).detach().numpy()
    return np.unique(best, return_inverse=True)[1]
