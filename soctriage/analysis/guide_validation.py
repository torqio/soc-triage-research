"""GUIDE thresholds selected on validation data: Table 3 (GUIDE block) and the full-automation sentence.

(1) Deferral threshold: tau = confidence at the 80% mark of each organization's validation ranking; test
    alerts with confidence >= tau are automated. The achieved test automation is reported, not matched.
(2) Full-automation thresholds on p(malicious), Neyman-Pearson on validation non-malicious scores: a fixed
    validation FPR of 5% (primary) and RiskFit's validation FPR at its default verdict (secondary).
    Organization-level recall differences: exact Wilcoxon, Holm within each target over a fixed family.
Conditions without validation rows (Opus) are omitted.

Outputs (outputs/guide/): validation_deferral_gate.csv, validation_fpr_thresholds.csv,
validation_fpr_threshold_tests.csv
"""

from __future__ import annotations

from .data import Inputs, has_val, loaded_methods
from .gates import counts, gate_tau, np_threshold, pooled, tau_validation, workflow
from .io import write_csv
from .methods import GROUP
from .stats import holm, wilcoxon_exact

FAMILY = [(a, b) for a in ("RiskFit", "CE") for b in ("Decisions + 1 ex.", "Decisions + 20 ex.", "Jev + 20 ex.")]
PRIMARY, SECONDARY = "val FPR 5% (primary)", "RiskFit validation FPR (secondary)"


def run(inp: Inputs) -> None:
    orgs, data = inp.guide()
    methods = loaded_methods(data)
    vm = [m for m in methods if has_val(data, m, orgs)]
    omitted = [m for m in methods if m not in vm]
    out = inp.out / "guide"

    dep = []
    for m in vm:
        pc = [counts(data[(m, o)]["test"], gate_tau(data[(m, o)]["test"], tau_validation(data[(m, o)]["val"], 0.8)))
              for o in orgs]
        w = workflow(pooled(pc))
        auto_org = [c["auto"] / c["n"] for c in pc]
        dep.append({"method": m, "group": GROUP[m], "rule": "tau at 80% validation coverage", **w,
                    "automation_min_org": min(auto_org), "automation_max_org": max(auto_org),
                    "weighted_cost_c10": 10 * w["misses"] + w["false_esc"]})
    dep += [{"method": m, "group": GROUP[m], "rule": "omitted: no validation rows"} for m in omitted]
    write_csv(out / "validation_deferral_gate.csv", dep)

    if "RiskFit" not in vm:
        return
    # RiskFit's validation FPR at its default (argmax) verdict, per organization
    rf_val_fpr = {}
    for o in orgs:
        neg = [r for r in data[("RiskFit", o)]["val"] if r["y"] != "mal"]
        rf_val_fpr[o] = sum(r["pred"] == "mal" for r in neg) / len(neg)
    targets = {PRIMARY: {o: 0.05 for o in orgs}, SECONDARY: rf_val_fpr}

    th, per_org_recall = [], {}
    for tname, target in targets.items():
        for m in vm:
            tp = fp = npos = nneg = 0
            recs = []
            for o in orgs:
                v, t = data[(m, o)]["val"], data[(m, o)]["test"]
                thr = np_threshold([r["pmal"] for r in v if r["y"] != "mal"], target[o])
                pos = [r for r in t if r["y"] == "mal"]
                neg = [r for r in t if r["y"] != "mal"]
                a = sum(r["pmal"] > thr for r in pos)
                b = sum(r["pmal"] > thr for r in neg)
                tp += a; fp += b; npos += len(pos); nneg += len(neg)
                recs.append(a / len(pos))
            per_org_recall[(tname, m)] = recs
            th.append({"target": tname, "method": m, "group": GROUP[m], "automation_rate": 1.0, "TP": tp,
                       "FN": npos - tp, "FP": fp, "TN": nneg - fp, "n_mal": npos, "n_nonmal": nneg,
                       "recall": tp / npos, "precision": tp / (tp + fp) if tp + fp else None,
                       "achieved_test_fpr": fp / nneg, "mean_org_recall": sum(recs) / len(recs),
                       "weighted_cost_c10": 10 * (npos - tp) + fp})
    th.append({"target": SECONDARY, "method": "(per-org targets)",
               "group": " ".join(f"{o}:{rf_val_fpr[o]:.4f}" for o in orgs)})
    write_csv(out / "validation_fpr_thresholds.csv", th)

    tests = []
    for tname in targets:
        rows = []
        for a, b in FAMILY:
            if (tname, a) not in per_org_recall or (tname, b) not in per_org_recall:
                continue
            d = [x - y for x, y in zip(per_org_recall[(tname, a)], per_org_recall[(tname, b)])]
            p, _, _ = wilcoxon_exact(d)
            rows.append({"target": tname, "local": a, "hosted": b, "mean_recall_diff": sum(d) / len(d),
                         "orgs_local_higher": sum(x > 0 for x in d), "orgs_local_lower": sum(x < 0 for x in d),
                         "orgs_tied": sum(x == 0 for x in d), "p_wilcoxon_exact": p})
        for r, ph in zip(rows, holm([r["p_wilcoxon_exact"] for r in rows])):
            r["p_holm"] = ph
        tests += rows
    write_csv(out / "validation_fpr_threshold_tests.csv", tests)
