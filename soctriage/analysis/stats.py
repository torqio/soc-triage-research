"""Exact Wilcoxon signed-rank test and Holm adjustment (standard library only)."""

from __future__ import annotations

import itertools


def wilcoxon_exact(diffs):
    """Exact two-sided Wilcoxon signed-rank p-value.

    Zeros are dropped; tied |d| get average ranks; the null distribution is enumerated over all 2^n sign
    patterns (n <= 12 organizations here). Returns (p, number of positive, number of negative differences).
    """
    d = [x for x in diffs if x != 0]
    n = len(d)
    if n == 0:
        return 1.0, 0, 0
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    total = sum(ranks)
    obs = min(w_plus, total - w_plus)
    hits = 0
    for signs in itertools.product((0, 1), repeat=n):
        w = sum(r for r, s in zip(ranks, signs) if s)
        if min(w, total - w) <= obs + 1e-9:
            hits += 1
    return hits / 2 ** n, sum(x > 0 for x in d), sum(x < 0 for x in d)


def holm(ps):
    """Holm step-down adjusted p-values, in the input order."""
    m = len(ps)
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda i: ps[i])):
        running = max(running, min(1.0, (m - rank) * ps[i]))
        adj[i] = running
    return adj
