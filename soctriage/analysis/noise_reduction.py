"""Noise reduction at the 80% gate: the share of non-malicious alerts closed without review (automated with a
non-malicious verdict), with workflow recall beside it. GUIDE and production.

GUIDE rows come from outputs/guide/gate80_workflow.csv (TN_auto = automated - (TP - deferred malicious) - FN - FP).
Production local rows use gate80_test_quantile.csv (malicious routed is released); hosted rows lack it there, so
their malicious-automated count comes from evasion.csv (condition 'none').
Output: outputs/noise_reduction.csv
"""

from __future__ import annotations

from .data import Inputs, read_csv
from .io import write_csv

ROUTED_PER_METHOD = 295  # every production method defers the same per-fold quantile


def run(inp: Inputs) -> None:
    rows = []
    for r in read_csv(inp.out / "guide" / "gate80_workflow.csv"):
        auto, tp, dm, fn, fp = (int(r[k]) for k in ("automated", "TP", "deferred_malicious", "FN", "FP"))
        nn = int(r["n_nonmal"])
        tn = auto - (tp - dm) - fn - fp
        rows.append({"dataset": "GUIDE", "method": r["method"], "auto_closed_nonmal": tn, "n_nonmal": nn,
                     "noise_reduction": tn / nn, "workflow_recall": float(r["workflow_recall"]),
                     "misses": fn, "false_esc": fp})
    evasion = {r["method"]: r for r in read_csv(inp.production / "evasion.csv")
               if r["gate"] == "test-quantile 80%" and r["condition"] == "none"}
    for r in read_csv(inp.production / "gate80_test_quantile.csv"):
        if r["scope"] != "all":
            continue
        nm, nn, mi, fe = int(r["n_mal"]), int(r["n_nonmal"]), int(r["misses"]), int(r["false_esc"])
        auto = int(r["n_alerts"]) - ROUTED_PER_METHOD
        if r["mal_routed"]:
            mal_auto = nm - int(r["mal_routed"])
        elif r["method"] in evasion:
            mal_auto = int(evasion[r["method"]]["malicious_automated"])
        else:
            continue
        tn = auto - mal_auto - fe
        rows.append({"dataset": "production", "method": r["method"], "auto_closed_nonmal": tn, "n_nonmal": nn,
                     "noise_reduction": tn / nn, "workflow_recall": (nm - mi) / nm, "misses": mi, "false_esc": fe})
    write_csv(inp.out / "noise_reduction.csv", rows)
