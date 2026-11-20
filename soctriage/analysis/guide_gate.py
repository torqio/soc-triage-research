"""GUIDE at a fixed review budget: Table 2 (GUIDE block), Figure 1 and the organization-level text.

Outputs (outputs/guide/):
  released_run_check.csv     the released per-prompt files reproduce the original 80%-gate table (sanity check)
  gate80_workflow.csv        pooled workflow confusion matrix and metrics at 80% automation, all 18 conditions
  coverage_sweep.csv         the same at automation rates 0.50, 0.55, ..., 1.00, with tie ranges (Figure 1)
  gate80_per_org.csv         per-organization misses and false escalations at 80%
  gate80_org_paired_tests.csv  fixed local-vs-hosted pairs: organizations lower/higher/tied, exact Wilcoxon
  gate80_cluster_bootstrap.csv organization-cluster bootstrap (2,000 replicates) of workflow recall and FE
"""

from __future__ import annotations

import random

from .data import Inputs, loaded_methods
from .gates import counts, gate_quantile, pooled, tie_range, workflow
from .io import write_csv
from .methods import GROUP
from .stats import wilcoxon_exact

COVERAGES = [round(0.5 + 0.05 * i, 2) for i in range(11)]
PAIRS = [("RiskFit", "Decisions + 20 ex."), ("CE", "Decisions + 20 ex."), ("Tiny Decision", "Decisions + 20 ex."),
         ("RiskFit", "Decisions + 1 ex."), ("RiskFit", "Opus + 1 ex."), ("RiskFit", "Jev + 20 ex.")]
BOOT_SEED, BOOT_REPLICATES = 20261112, 2000

# The original release's 80%-gate table (misses, false escalations) and two 100% rows. The released
# per-prompt files must reproduce them before any new number is trusted.
RELEASED_GATE80 = {
    "RiskFit": (11, 46), "CE": (15, 35), "LightGBM": (31, 39), "MaxSim": (38, 17), "kNN": (21, 28),
    "Tiny Decision": (12, 30), "Decisions 0-shot": (0, 497), "Decisions + 1 ex.": (8, 420),
    "Decisions + 5 ex.": (24, 109), "Decisions + 20 ex.": (12, 90), "Jev 0-shot": (4, 492), "Jev + 1 ex.": (27, 381),
    "Jev + 5 ex.": (38, 245), "Jev + 20 ex.": (29, 213), "Opus 0-shot": (5, 490), "Opus + 1 ex.": (16, 241),
    "CyberSecQwen-4B": (0, 502), "Qwen3-4B base": (59, 437)}
RELEASED_GATE100 = {"RiskFit": (25, 79), "Decisions + 1 ex.": (24, 500)}


def per_org_counts(data, orgs, method, coverage):
    return [counts(data[(method, o)]["test"], gate_quantile(data[(method, o)]["test"], coverage)) for o in orgs]


def released_run_check(inp: Inputs) -> bool:
    orgs, data = inp.guide()
    rows, ok = [], True
    for cov, expected in ((0.8, RELEASED_GATE80), (1.0, RELEASED_GATE100)):
        for m in loaded_methods(data):
            c = pooled(per_org_counts(data, orgs, m, cov))
            got = (c["fn"], c["fp"])
            match = expected.get(m) in (None, got)
            ok &= match
            rows.append({"coverage": cov, "method": m, "misses": got[0], "false_esc": got[1],
                         "paper": "" if m not in expected else f"{expected[m][0]}/{expected[m][1]}",
                         "match": "" if m not in expected else match})
    write_csv(inp.out / "guide" / "released_run_check.csv", rows)
    return ok


def run(inp: Inputs) -> None:
    orgs, data = inp.guide()
    methods = loaded_methods(data)
    per, sweep = {}, []
    for m in methods:
        for cov in COVERAGES:
            pc = per_org_counts(data, orgs, m, cov)
            per[(m, cov)] = pc
            tr = [tie_range(data[(m, o)]["test"], cov) for o in orgs]
            w = workflow(pooled(pc))
            sweep.append({"method": m, "group": GROUP[m], "target_coverage": cov, **w,
                          "misses_tie_min": sum(t["miss_min"] for t in tr),
                          "misses_tie_max": sum(t["miss_max"] for t in tr),
                          "fe_tie_min": sum(t["fe_min"] for t in tr), "fe_tie_max": sum(t["fe_max"] for t in tr),
                          "weighted_cost_c10": 10 * w["misses"] + w["false_esc"]})
    out = inp.out / "guide"
    write_csv(out / "coverage_sweep.csv", sweep)
    write_csv(out / "gate80_workflow.csv", [r for r in sweep if r["target_coverage"] == 0.8])

    write_csv(out / "gate80_per_org.csv", [
        {"method": m, "org": o, "n": c["n"], "n_mal": c["n_mal"], "automated": c["auto"],
         "misses": c["fn"], "false_esc": c["fp"]}
        for m in methods for o, c in zip(orgs, per[(m, 0.8)])])

    paired = []
    for a, b in PAIRS:
        if (a, 0.8) not in per or (b, 0.8) not in per:
            continue
        ca, cb = per[(a, 0.8)], per[(b, 0.8)]
        for metric, key in (("misses", "fn"), ("false_esc", "fp")):
            d = [x[key] - y[key] for x, y in zip(ca, cb)]
            p, _, _ = wilcoxon_exact(d)
            paired.append({"local": a, "hosted": b, "metric": metric, "local_total": sum(x[key] for x in ca),
                           "hosted_total": sum(y[key] for y in cb), "orgs_local_lower": sum(x < 0 for x in d),
                           "orgs_local_higher": sum(x > 0 for x in d), "orgs_tied": sum(x == 0 for x in d),
                           "wilcoxon_exact_p_two_sided": p,
                           "per_org_diff_local_minus_hosted": " ".join(map(str, d))})
    write_csv(out / "gate80_org_paired_tests.csv", paired)

    # Organization-cluster bootstrap: resample the 12 organizations with replacement. The resampling indices
    # are drawn once and shared by all methods.
    rng = random.Random(BOOT_SEED)
    B = BOOT_REPLICATES
    idx = [[rng.randrange(len(orgs)) for _ in orgs] for _ in range(B)]

    def q(v):
        s = sorted(v)
        return s[int(0.025 * B)], s[int(0.975 * B) - 1]

    boot = []
    for m in methods:
        rec, fe, prec = [], [], []
        for sample in idx:
            w = workflow(pooled([per[(m, 0.8)][i] for i in sample]))
            rec.append(w["workflow_recall"]); fe.append(w["false_esc"]); prec.append(w["workflow_precision"])
        w0 = workflow(pooled(per[(m, 0.8)]))
        boot.append({"method": m, "workflow_recall": w0["workflow_recall"], "recall_lo": q(rec)[0],
                     "recall_hi": q(rec)[1], "false_esc": w0["false_esc"], "fe_lo": q(fe)[0], "fe_hi": q(fe)[1],
                     "workflow_precision": w0["workflow_precision"], "precision_lo": q(prec)[0],
                     "precision_hi": q(prec)[1], "replicates": B,
                     "resampling_unit": "organization (12, with replacement)", "seed": BOOT_SEED})
    write_csv(out / "gate80_cluster_bootstrap.csv", boot)
