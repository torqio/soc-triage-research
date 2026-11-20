"""Confidence gates, validation thresholds and workflow metrics (Methods: "Task and Evaluation Protocol").

A gate automates the highest-confidence alerts of an organization (or tenant-fold) and defers the rest to an
analyst, who is assumed to resolve them correctly. Records are dicts with ``id``, ``y`` (true label), ``pred``
(verdict), ``conf`` (gate confidence) and ``pmal`` (p(malicious) score); labels are mal / ben / fp / unresolved.
These rules re-implement ``soctriage/evaluation.py`` (ranked, gate, tau_validation, np_threshold) in pure Python.
"""

from __future__ import annotations

import math

COUNT_KEYS = ("n", "n_mal", "auto", "tp_auto", "fn", "fp", "tn_auto", "deferred_mal", "deferred_non")


def ranked(recs):
    """Highest confidence first; ties broken by prompt id as UTF-8 bytes."""
    return sorted(recs, key=lambda r: (-r["conf"], r["id"].encode("utf-8")))


def n_keep(coverage: float, n: int) -> int:
    """Number of alerts automated at a target coverage: ceil(coverage * n)."""
    return min(n, math.ceil(round(coverage * n, 9)))


def gate_quantile(test, coverage: float) -> set[str]:
    """Retrospective matched coverage: automate the top ceil(coverage * n) test alerts."""
    rk = ranked(test)
    return {r["id"] for r in rk[:n_keep(coverage, len(rk))]}


def gate_tau(test, tau: float) -> set[str]:
    """Fixed numerical threshold: automate alerts with confidence >= tau."""
    return {r["id"] for r in test if r["conf"] >= tau}


def tau_validation(val, coverage: float = 0.8) -> float:
    """Deferral threshold: the confidence of the alert at the coverage mark of the validation ranking."""
    rv = ranked(val)
    return rv[n_keep(coverage, len(rv)) - 1]["conf"]


def np_threshold(neg_scores, target_fpr: float) -> float:
    """Neyman-Pearson threshold on validation non-malicious scores: flag if score > threshold."""
    s = sorted(neg_scores, reverse=True)
    m = math.floor(round(target_fpr * len(s), 9))
    return -1.0 if m >= len(s) else s[m]


def counts(test, kept_ids) -> dict[str, int]:
    """Workflow confusion counts for one organization, given the set of automated ids."""
    c = dict.fromkeys(COUNT_KEYS, 0)
    c["n"] = len(test)
    for r in test:
        mal = r["y"] == "mal"
        c["n_mal"] += mal
        if r["id"] in kept_ids:
            c["auto"] += 1
            pm = r["pred"] == "mal"
            if mal and pm:
                c["tp_auto"] += 1
            elif mal:
                c["fn"] += 1
            elif pm:
                c["fp"] += 1
            else:
                c["tn_auto"] += 1
        elif mal:
            c["deferred_mal"] += 1
        else:
            c["deferred_non"] += 1
    return c


def pooled(per_org) -> dict[str, int]:
    return {k: sum(c[k] for c in per_org) for k in COUNT_KEYS}


def workflow(c) -> dict:
    """Workflow metrics from pooled counts; deferred alerts count as correctly resolved.

    TP = automated true positives + deferred malicious; FN = unreviewed misses; FP = false escalations;
    TN = automated true negatives + deferred non-malicious.
    """
    tp = c["tp_auto"] + c["deferred_mal"]
    fn, fp = c["fn"], c["fp"]
    tn = c["tn_auto"] + c["deferred_non"]
    n = c["n"]
    return dict(n=n, n_mal=c["n_mal"], n_nonmal=n - c["n_mal"], automated=c["auto"], deferred=n - c["auto"],
                automation_rate=c["auto"] / n, TP=tp, FN=fn, FP=fp, TN=tn,
                misses=fn, false_esc=fp,
                workflow_precision=tp / (tp + fp) if tp + fp else None,
                workflow_recall=tp / (tp + fn) if tp + fn else None,
                deferred_malicious=c["deferred_mal"])


def tie_range(test, coverage: float) -> dict[str, int]:
    """Min/max misses and false escalations over all orders of the alerts tied at the gate cutoff."""
    rk = ranked(test)
    kk = n_keep(coverage, len(rk))
    if kk == 0:
        return dict(miss_min=0, miss_max=0, fe_min=0, fe_max=0, n_tied=0)
    tau = rk[kk - 1]["conf"]
    above = [r for r in test if r["conf"] > tau]
    tied = [r for r in test if r["conf"] == tau]
    kt = kk - len(above)

    def miss(rs):
        return sum(r["y"] == "mal" and r["pred"] != "mal" for r in rs)

    def fe(rs):
        return sum(r["y"] != "mal" and r["pred"] == "mal" for r in rs)

    ma, fa, mt, ft = miss(above), fe(above), miss(tied), fe(tied)
    return dict(miss_min=ma + max(0, kt - (len(tied) - mt)), miss_max=ma + min(kt, mt),
                fe_min=fa + max(0, kt - (len(tied) - ft)), fe_max=fa + min(kt, ft), n_tied=len(tied))
