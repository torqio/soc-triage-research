"""Production results from the released AGGREGATES (no alert-level data exists in this repository).

As in the paper, deferred alerts receive correct verdicts. Pooled over tenants: TP = n_mal - misses,
FN = misses, FP = false escalations; workflow precision = TP / (TP + FP), recall = TP / n_mal.

Outputs (outputs/production/):
  gate80_workflow.csv            Table 2 production block (80% test-quantile gate, seed 42)
  validation_deferral_gate.csv   Table 3 production block (deferral threshold from validation)
  default_verdicts_workflow.csv  full coverage (default verdicts)
  seeds_workflow.csv             seven seeds of RiskFit and CE-A100 at both gates
  later_tenant_a_workflow.csv    Table 3 tenant A later-alert block
  validation_fpr5_thresholds.csv full automation at a 5% validation FPR
  hinge_by_sampling_seeds.csv    Table 4: per-seed sums from the tenant x fold x seed units
  confidence_ranking.csv         accuracy of automated alerts at 100% vs 80% coverage (paper: Confidence ranking)
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict

from .data import Inputs, read_csv
from .io import write_csv

LATER_A_ALERTS, LATER_A_MALICIOUS = 433, 11
PRODUCTION_MALICIOUS = 73


def wf(n, n_mal, misses, fe, automated):
    tp = n_mal - misses
    return {"n": n, "n_mal": n_mal, "automated": automated,
            "automation_rate": automated / n if automated is not None else None,
            "deferred": n - automated if automated is not None else None, "misses": misses, "false_esc": fe,
            "TP": tp, "FN": misses, "FP": fe, "workflow_precision": tp / (tp + fe) if tp + fe else None,
            "workflow_recall": tp / n_mal, "weighted_cost_c10": 10 * misses + fe}


def run(inp: Inputs) -> None:
    def rd(name):
        return read_csv(inp.production / name)

    out = inp.out / "production"

    g = rd("gate80_test_quantile.csv")
    # hosted rows leave routed_alerts empty: every method defers the same per-fold quantile
    auto_tq = {r["scope"]: int(r["n_alerts"]) - int(r["routed_alerts"]) for r in g if r["routed_alerts"]}
    write_csv(out / "gate80_workflow.csv", [
        {"method": r["method"], "scope": r["scope"], "gate": "test-quantile 80% (retrospective)", "seed": 42,
         **wf(int(r["n_alerts"]), int(r["n_mal"]), int(r["misses"]), int(r["false_esc"]), auto_tq[r["scope"]]),
         "misses_ci95": f"{r['misses_ci95_low']}-{r['misses_ci95_high']}",
         "fe_ci95": f"{r['false_esc_ci95_low']}-{r['false_esc_ci95_high']}",
         "note": "" if r["routed_alerts"] else "automated count equals the other methods' by construction (same per-fold quantile)"}
        for r in g])

    rows = []
    for r in rd("deployable_gate.csv"):
        if r["scope"] != "all":
            rows.append({"method": r["method"], "scope": r["scope"], "misses": r["misses"],
                         "automation_rate": r["automated_share"] or None})
            continue
        rows.append({"method": r["method"], "scope": "all", "gate": "deployable (tau at 80% validation coverage)",
                     "seed": 42, **wf(int(r["n_alerts"]), PRODUCTION_MALICIOUS, int(r["misses"]), int(r["false_esc"]),
                                      int(r["automated"])),
                     "misses_ci95": f"{r['misses_ci95_low']}-{r['misses_ci95_high']}"})
    write_csv(out / "validation_deferral_gate.csv", rows)

    rows = []
    for r in rd("default_verdicts.csv"):
        nm, nn = int(r["n_mal"]), int(r["n_nonmal"])
        rows.append({"method": r["method"], "scope": r["scope"], "operating_point": "default verdict, 100% automated",
                     **wf(nm + nn, nm, nm - int(r["caught"]), int(r["false_esc"]), nm + nn)})
    write_csv(out / "default_verdicts_workflow.csv", rows)

    # seven seeds (RiskFit, CE-A100): per-seed totals; deployable automation from the unit file
    dep_auto, ntest = defaultdict(int), defaultdict(int)
    for u in rd("units/seeds_riskfit_vs_ce_7seeds_units.csv"):
        k = (u["seed"], u["arm"])
        dep_auto[k] += int(u["dep_auto"])
        ntest[k] += int(u["n_test"])
    rows, summary = [], defaultdict(lambda: defaultdict(list))
    for r in rd("seeds_riskfit_vs_ce_7seeds.csv"):
        k = (r["seed"], r["arm"])
        n = ntest[k]
        tq = wf(n, PRODUCTION_MALICIOUS, int(r["tq_misses"]), int(r["tq_fe"]), None)
        dp = wf(n, PRODUCTION_MALICIOUS, int(r["dep_misses"]), int(r["dep_fe"]), dep_auto[k])
        fc = wf(n, PRODUCTION_MALICIOUS, PRODUCTION_MALICIOUS - int(r["caught"]), int(r["fe"]), n)
        rows.append({"seed": r["seed"], "arm": r["arm"], "n": n,
                     "tq_misses": tq["misses"], "tq_fe": tq["false_esc"], "tq_precision": tq["workflow_precision"],
                     "tq_recall": tq["workflow_recall"], "dep_automation": dp["automation_rate"],
                     "dep_misses": dp["misses"], "dep_fe": dp["false_esc"], "dep_precision": dp["workflow_precision"],
                     "dep_recall": dp["workflow_recall"], "full_misses": fc["misses"], "full_fe": fc["false_esc"]})
        for key in ("tq_misses", "tq_fe", "dep_automation", "dep_misses", "dep_fe", "full_misses", "full_fe"):
            summary[r["arm"]][key].append(rows[-1][key])
    for arm, vals in summary.items():
        rows.append({"seed": "mean", "arm": arm, **{k: st.mean(v) for k, v in vals.items()}})
        rows.append({"seed": "sd (across 7 seeds)", "arm": arm, **{k: st.stdev(v) for k, v in vals.items()}})
    write_csv(out / "seeds_workflow.csv", rows)

    write_csv(out / "later_tenant_a_workflow.csv", [
        {"method": r["method"], "gate": r["gate"] or "none (100% automated)",
         **wf(LATER_A_ALERTS, LATER_A_MALICIOUS, int(r["unreviewed_misses"]), int(r["false_escalations"]),
              int(r["test_automated"]))}
        for r in rd("later_alerts_tenantA_gates.csv")])

    rows = []
    for r in rd("thresholds.csv"):
        if r["operating_point"] == "FPR 5%" and r["scope"] == "all":
            nm, nn = int(r["n_mal"]), int(r["n_nonmal"])
            rows.append({"method": r["method"], "score": r["score"], "selection": r["selection"],
                         "operating_point": "validation FPR 5% (fixed target)",
                         **wf(nm + nn, nm, nm - int(r["caught"]), int(r["false_esc"]), nm + nn)})
    write_csv(out / "validation_fpr5_thresholds.csv", rows)

    # Table 4: recompute per-seed totals from the tenant x fold x seed units and check the arms file
    sums = defaultdict(lambda: defaultdict(int))
    for u in rd("units/hinge_by_sampling_units.csv"):
        k = (u["sampling"], u["loss"], u["seed"])
        for f in ("caught", "fe", "n_mal"):
            sums[k][f] += int(u[f])
    rows = []
    for a in rd("hinge_by_sampling_arms.csv"):
        seeds = sorted({k[2] for k in sums if k[0] == a["sampling"] and k[1] == a["loss"]})
        caught = [sums[(a["sampling"], a["loss"], s)]["caught"] for s in seeds]
        fe = [sums[(a["sampling"], a["loss"], s)]["fe"] for s in seeds]
        rows.append({"sampling": a["sampling"], "loss": a["loss"], "seeds": "/".join(seeds),
                     "caught_per_seed_units": "/".join(map(str, caught)), "caught_per_seed_arms_file": a["caught_per_seed"],
                     "caught_mean": st.mean(caught), "caught_sd_across_seeds": st.stdev(caught),
                     "fe_per_seed_units": "/".join(map(str, fe)), "fe_mean": st.mean(fe),
                     "fe_sd_across_seeds": st.stdev(fe),
                     "n_mal_per_seed": sums[(a["sampling"], a["loss"], seeds[0])]["n_mal"],
                     "consistent_with_arms_file": "/".join(map(str, caught)) == a["caught_per_seed"]})
    write_csv(out / "hinge_by_sampling_seeds.csv", rows)

    # Confidence ranking: accuracy of the automated alerts at 100% and 80% coverage (pooled over folds)
    acc = {(r["tenant"], r["method"], r["coverage"]): r["accuracy_of_automated_alerts"]
           for r in rd("accuracy_at_coverage.csv")}
    write_csv(out / "confidence_ranking.csv", [
        {"method": m, "tenant": t, "accuracy_automated_at_100": float(acc[(t, m, "1.00")]),
         "accuracy_automated_at_80": float(acc[(t, m, "0.80")])}
        for (t, m, cov) in acc if cov == "1.00"])
