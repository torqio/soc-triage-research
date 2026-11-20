"""Check the numbers printed in the paper against the analysis outputs and the released aggregates.

Each claim is (where in the paper, the exact string printed in main.tex, a source table, a row filter, a
formatter). The formatter turns the source value into the string the paper should print; the claim passes when
that string equals the printed one AND the printed string occurs verbatim in main.tex. A claim with no row filter
receives the whole table (for ranges such as "69--80\\%").

KNOWN_ISSUES lists printed values that do not match the released data; they are reported, not failed.
Writes outputs/claims_check.csv. Returns the number of failed claims.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .data import Inputs, read_csv
from .methods import LOCAL


# ----------------------------------------------------------------------------------------------- formatters
def i(x):
    return str(int(round(float(x))))


def p3(x):
    """.906 style (no leading zero below 1)."""
    v = f"{float(x):.3f}"
    return v[1:] if v.startswith("0.") else v


def p2(x):
    v = f"{float(x):.2f}"
    return v[1:] if v.startswith("0.") else v


def pct0(x):
    return f"{round(100 * float(x))}"


def pct1(x):
    return f"{100 * float(x):.1f}\\%"


def f1(x):
    return f"{float(x):.1f}"


def prec(r):
    return p3(int(r["TP"]) / (int(r["TP"]) + int(r["FP"])))


def rec(r):
    return p3(int(r["TP"]) / (int(r["TP"]) + int(r["FN"])))


def auto(r):
    return pct1(int(r["automated"]) / int(r["n"]))


def pm(a, b):
    return f"{a} $\\pm$ {b}"


def rng(values, fmt=str, sep="--"):
    return f"{fmt(min(values))}{sep}{fmt(max(values))}"


EXACT = {"workflow_precision": prec, "workflow_recall": rec, "automation_rate": auto}
NUMBER_WORDS = {6: "six"}


@dataclass
class Claim:
    where: str
    printed: str | None
    source: str               # "guide/<file>", "production/<file>", "<file>" (outputs/) or "data:<file>" (aggregates)
    match: dict | None
    fn: Callable


CLAIMS: list[Claim] = []
KNOWN_ISSUES: list[tuple[Claim, str]] = []


def add(where, printed, source, match, fn):
    CLAIMS.append(Claim(where, printed, source, match, fn))


def known(where, printed, source, match, fn, note):
    KNOWN_ISSUES.append((Claim(where, printed, source, match, fn), note))


G80, SWEEP, PAIRED, BOOT = "guide/gate80_workflow.csv", "guide/coverage_sweep.csv", "guide/gate80_org_paired_tests.csv", "guide/gate80_cluster_bootstrap.csv"
GDEP, GTH, GTT = "guide/validation_deferral_gate.csv", "guide/validation_fpr_thresholds.csv", "guide/validation_fpr_threshold_tests.csv"
TASK, IW, IC = "guide/task_label_conflicts.csv", "guide/incident_weighted.csv", "guide/incident_concentration.csv"
PG, PD, PF = "production/gate80_workflow.csv", "production/validation_deferral_gate.csv", "production/default_verdicts_workflow.csv"
SEEDS, LATER, HINGE = "production/seeds_workflow.csv", "production/later_tenant_a_workflow.csv", "production/hinge_by_sampling_seeds.csv"
RANK, NOISE = "production/confidence_ranking.csv", "noise_reduction.csv"
HOSTED_01 = ["Decisions 0-shot", "Decisions + 1 ex.", "Jev 0-shot", "Jev + 1 ex.", "Opus 0-shot", "Opus + 1 ex."]
PROD_LOCAL = ["RiskFit", "CE", "Tiny Decision", "kNN (frozen)", "LightGBM", "MaxSim"]
TOP3 = ["RiskFit", "CE", "Tiny Decision"]


def where_in(rows, key, names, **flt):
    return [r for r in rows if r[key] in names and all(r.get(k) == v for k, v in flt.items())]


# ----------------------------------------------------------------------------------------------- Abstract, data
add("Data: production alerts", "We use 1,492 alerts", "data:data_summary.csv", {"tenant": "all"},
    lambda r: f"We use {int(r['alerts']):,} alerts")
add("Data: per-tenant counts", "(412, 707 and 373 alerts; 17, 39 and 17 malicious)", "data:data_summary.csv", None,
    lambda rows: "({}, {} and {} alerts; {}, {} and {} malicious)".format(
        *[r["alerts"] for r in rows[:3]], *[r["tp_malicious"] for r in rows[:3]]))
add("Data: corrections", "528", "data:data_summary.csv", {"tenant": "all"}, lambda r: i(r["analyst_corrections"]))
add("Data: corrections to malicious", "only six of them to malicious", "data:data_summary.csv", {"tenant": "all"},
    lambda r: f"only {NUMBER_WORDS[int(r['malicious_corrections'])]} of them to malicious")
add("Data: uncorrected equal to LLM verdict", "943 of the 964 uncorrected labels", "data:data_summary.csv",
    {"tenant": "all"}, lambda r: f"{i(r['uncorrected_equal_llm_export_verdict'])} of the {i(r['uncorrected'])} uncorrected labels")
add("Data: tenant A exact duplicates", "33.5\\%", "data:near_duplicates.csv", {"tenant": "A", "test_alerts": "all"},
    lambda r: f"{100 * float(r['share_exact_dup_ws_case_norm']):.1f}\\%")
add("Data: Response field", "identifies 7 of the 17 malicious alerts", "data:facts.csv",
    {"quantity": "Tenant A malicious test alerts marked by one vendor Response value (100% precision)"},
    lambda r: "identifies {} of the {} malicious alerts".format(*r["value"].split(" of ")))
add("Data: later tenant A alerts", "433 further alerts (11 malicious)", "data:later_alerts_tenantA_full_coverage.csv",
    {"method": "RiskFit"}, lambda r: f"{r['n']} further alerts ({r['n_mal']} malicious)")
LC = {"level": "all", "org": "all", "split": "all"}
add("GUIDE: incidents", "71,576", TASK, LC, lambda r: f"{int(r['incidents']):,}")
add("GUIDE: prompts", "7,160", TASK, LC, lambda r: f"{int(r['prompts']):,}")
add("GUIDE: mixed prompts", "414 prompts (5.8\\%)", TASK, LC,
    lambda r: f"{i(r['mixed_prompts'])} prompts ({100 * int(r['mixed_prompts']) / int(r['prompts']):.1f}\\%)")
add("GUIDE: conflicting incidents", "3.2\\%", TASK, LC,
    lambda r: f"{100 * int(r['conflicting_incidents']) / int(r['incidents']):.1f}\\%")
add("GUIDE: test set", "1,079 prompts (456 malicious, 623 non-malicious)", G80, {"method": "RiskFit"},
    lambda r: f"{int(r['n']):,} prompts ({r['n_mal']} malicious, {r['n_nonmal']} non-malicious)")
add("GUIDE: test incidents", "9,722", TASK, {"level": "all", "org": "all", "split": "test"},
    lambda r: f"{int(r['incidents']):,}")
add("GUIDE: 11 largest prompts", "52\\%", IC, {"quantity": "share of test incidents in the 11 largest test prompts (1%)"},
    lambda r: f"{round(100 * float(r['value']))}\\%")

# ----------------------------------------------------------------------------------------------- Table 2 (GUIDE)
for m, vals in {"RiskFit": ("11", "46", ".906", ".976"), "CE": ("15", "35", ".926", ".967"),
                "Tiny Decision": ("12", "30", ".937", ".974"), "kNN": ("21", "28", ".940", ".954"),
                "LightGBM": ("31", "39", ".916", ".932"), "MaxSim": ("38", "17", ".961", ".917"),
                "Decisions 0-shot": ("0", "497", ".478", "1.000"), "Decisions + 1 ex.": ("8", "420", ".516", ".982"),
                "Decisions + 5 ex.": ("24", "109", ".799", ".947"), "Decisions + 20 ex.": ("12", "90", ".831", ".974"),
                "Jev + 20 ex.": ("29", "213", ".667", ".936"), "Opus + 1 ex.": ("16", "241", ".646", ".965"),
                "CyberSecQwen-4B": ("0", "502", ".476", "1.000")}.items():
    add(f"Table 2 GUIDE {m} misses", vals[0], G80, {"method": m}, lambda r: i(r["misses"]))
    add(f"Table 2 GUIDE {m} FE", vals[1], G80, {"method": m}, lambda r: i(r["false_esc"]))
    add(f"Table 2 GUIDE {m} workflow precision", vals[2], G80, {"method": m}, prec)
    add(f"Table 2 GUIDE {m} workflow recall", vals[3], G80, {"method": m}, rec)
add("Table 2 GUIDE automated", "868", G80, {"method": "RiskFit"}, lambda r: i(r["automated"]))
add("Table 2 GUIDE automation rate", "80.4\\%", G80, {"method": "RiskFit"}, auto)
add("Table 2 kNN tie range", "19--21", SWEEP, {"method": "kNN", "target_coverage": "0.8000"},
    lambda r: f"{i(r['misses_tie_min'])}--{i(r['misses_tie_max'])}")
add("Table 2 Opus tie range (misses)", "10--21", SWEEP, {"method": "Opus + 1 ex.", "target_coverage": "0.8000"},
    lambda r: f"{i(r['misses_tie_min'])}--{i(r['misses_tie_max'])}")
add("Table 2 Opus tie range (FE)", "236--251", SWEEP, {"method": "Opus + 1 ex.", "target_coverage": "0.8000"},
    lambda r: f"{i(r['fe_tie_min'])}--{i(r['fe_tie_max'])}")

# ----------------------------------------------------------------------------------------------- Table 2 (production)
for m, vals in {"RiskFit": ("9", "28", ".696", ".877"), "CE": ("9", "8", ".889", ".877"),
                "Tiny Decision": ("10", "5", ".926", ".863"), "kNN (frozen)": ("16", "2", ".966", ".781"),
                "LightGBM": ("13", "6", ".909", ".822"), "MaxSim": ("7", "4", ".943", ".904"),
                "Decisions zero-shot": ("1", "945", ".071", ".986"), "Decisions + exemplar": ("0", "154", ".322", "1.000"),
                "Gemini + exemplar": ("11", "41", ".602", ".849")}.items():
    flt = {"method": m, "scope": "all"}
    add(f"Table 2 production {m} misses", vals[0], PG, flt, lambda r: i(r["misses"]))
    add(f"Table 2 production {m} FE", vals[1], PG, flt, lambda r: i(r["false_esc"]))
    add(f"Table 2 production {m} workflow precision", vals[2], PG, flt, prec)
    add(f"Table 2 production {m} workflow recall", vals[3], PG, flt, rec)
add("Table 2 production automated", "1,197", PG, {"method": "RiskFit", "scope": "all"},
    lambda r: f"{int(r['automated']):,}")
add("Table 2 production automation rate", "80.2\\%", PG, {"method": "RiskFit", "scope": "all"}, auto)

# ----------------------------------------------------------------------------------------------- GUIDE text (fixed budget)
add("GUIDE text: hosted <=1 ex. and CyberSecQwen misses", "missed 0 to 16 malicious prompts", G80, None,
    lambda rows: "missed {} malicious prompts".format(rng([int(r["misses"]) for r in where_in(
        rows, "method", [m for m in HOSTED_01 if m != "Jev + 1 ex."] + ["CyberSecQwen-4B"])], sep=" to ")))
add("GUIDE text: Jev + 1 ex. misses", "(Jev with one exemplar: 27)", G80, {"method": "Jev + 1 ex."},
    lambda r: f"(Jev with one exemplar: {i(r['misses'])})")
add("GUIDE text: hosted <=1 ex. and CyberSecQwen FE", "escalated 241 to 502", G80, None,
    lambda rows: "escalated " + rng([int(r["false_esc"]) for r in where_in(rows, "method", HOSTED_01 + ["CyberSecQwen-4B"])], sep=" to "))
add("GUIDE text: hosted <=1 ex. precision", "(workflow precision .48--.65)", G80, None,
    lambda rows: "(workflow precision {})".format(rng([int(r["TP"]) / (int(r["TP"]) + int(r["FP"]))
                                                       for r in where_in(rows, "method", HOSTED_01 + ["CyberSecQwen-4B"])], p2)))
add("GUIDE text: RiskFit vs D20 misses by organization", "RiskFit fewer in 3 organizations, more in 3, tied in 6", PAIRED,
    {"local": "RiskFit", "hosted": "Decisions + 20 ex.", "metric": "misses"},
    lambda r: f"RiskFit fewer in {r['orgs_local_lower']} organizations, more in {r['orgs_local_higher']}, tied in {r['orgs_tied']}")
add("GUIDE text: RiskFit vs D20 misses p", "0.97", PAIRED, {"local": "RiskFit", "hosted": "Decisions + 20 ex.", "metric": "misses"},
    lambda r: f"{float(r['wilcoxon_exact_p_two_sided']):.2f}")
add("GUIDE text: CE vs D20 FE organizations", "10 of 12", PAIRED, {"local": "CE", "hosted": "Decisions + 20 ex.", "metric": "false_esc"},
    lambda r: f"{r['orgs_local_lower']} of 12")
add("GUIDE text: Tiny vs D20 FE organizations", "10 of 12", PAIRED,
    {"local": "Tiny Decision", "hosted": "Decisions + 20 ex.", "metric": "false_esc"}, lambda r: f"{r['orgs_local_lower']} of 12")
add("GUIDE text: CE vs D20 FE p", "0.005", PAIRED, {"local": "CE", "hosted": "Decisions + 20 ex.", "metric": "false_esc"},
    lambda r: f"{float(r['wilcoxon_exact_p_two_sided']):.3f}")
add("GUIDE text: Tiny vs D20 FE p", "0.005", PAIRED, {"local": "Tiny Decision", "hosted": "Decisions + 20 ex.", "metric": "false_esc"},
    lambda r: f"{float(r['wilcoxon_exact_p_two_sided']):.3f}")
add("GUIDE text: RiskFit vs D20 FE p", "0.066", PAIRED, {"local": "RiskFit", "hosted": "Decisions + 20 ex.", "metric": "false_esc"},
    lambda r: f"{float(r['wilcoxon_exact_p_two_sided']):.3f}")
add("GUIDE text: RiskFit vs D20 FE organizations", "7 lower, 2 higher, 3 tied", PAIRED,
    {"local": "RiskFit", "hosted": "Decisions + 20 ex.", "metric": "false_esc"},
    lambda r: f"{r['orgs_local_lower']} lower, {r['orgs_local_higher']} higher, {r['orgs_tied']} tied")
add("GUIDE text: bootstrap RiskFit recall", ".948--.991", BOOT, {"method": "RiskFit"}, lambda r: f"{p3(r['recall_lo'])}--{p3(r['recall_hi'])}")
add("GUIDE text: bootstrap RiskFit FE", "21--71", BOOT, {"method": "RiskFit"}, lambda r: f"{i(r['fe_lo'])}--{i(r['fe_hi'])}")
add("GUIDE text: bootstrap D20 recall", ".926--.993", BOOT, {"method": "Decisions + 20 ex."}, lambda r: f"{p3(r['recall_lo'])}--{p3(r['recall_hi'])}")
add("GUIDE text: bootstrap D20 FE", "47--137", BOOT, {"method": "Decisions + 20 ex."}, lambda r: f"{i(r['fe_lo'])}--{i(r['fe_hi'])}")

# ----------------------------------------------------------------------------------------------- production text
add("Production text: local misses and FE", "the local classifiers missed 7 to 16 with 2 to 28 false escalations", PG, None,
    lambda rows: "the local classifiers missed {} with {} false escalations".format(
        rng([int(r["misses"]) for r in where_in(rows, "method", PROD_LOCAL, scope="all")], sep=" to "),
        rng([int(r["false_esc"]) for r in where_in(rows, "method", PROD_LOCAL, scope="all")], sep=" to ")))
add("Production text: Gemini confidence values", "at most six distinct values per fold", "data:facts.csv",
    {"quantity": "Gemini 2.5 Pro distinct verbalized confidence values per fold (maximum)"},
    lambda r: f"at most {NUMBER_WORDS[int(r['value'])]} distinct values per fold")
for arm, label, m_txt, fe_txt in (("RiskFit", "RiskFit", "9.3 $\\pm$ 2.0", "16.0 $\\pm$ 6.2"),
                                  ("CE-A100 (lambda=0)", "CE", "9.3 $\\pm$ 2.6", "11.3 $\\pm$ 3.4")):
    sd = {"seed": "sd (across 7 seeds)", "arm": arm}
    add(f"Production text: seven seeds {label} misses", m_txt, SEEDS, {"seed": "mean", "arm": arm},
        lambda r, sd=sd: pm(f1(r["tq_misses"]), f1(rows_of(SEEDS, sd)["tq_misses"])))
    add(f"Production text: seven seeds {label} FE", fe_txt, SEEDS, {"seed": "mean", "arm": arm},
        lambda r, sd=sd: pm(f1(r["tq_fe"]), f1(rows_of(SEEDS, sd)["tq_fe"])))
add("Production text: RiskFit seed ranges", "(range 5--11) with 16.0 $\\pm$ 6.2 false escalations (9--28)", SEEDS, None,
    lambda rows: "(range {}) with 16.0 $\\pm$ 6.2 false escalations ({})".format(
        rng([int(r["tq_misses"]) for r in rows if r["arm"] == "RiskFit" and r["seed"].isdigit()]),
        rng([int(r["tq_fe"]) for r in rows if r["arm"] == "RiskFit" and r["seed"].isdigit()])))

# ----------------------------------------------------------------------------------------------- noise reduction, ranking, cost
add("Noise reduction: GUIDE", "69--80\\% of non-malicious GUIDE prompts against 63\\%", NOISE, None,
    lambda rows: "{}\\% of non-malicious GUIDE prompts against {}\\%".format(
        rng([float(r["noise_reduction"]) for r in where_in(rows, "method", list(LOCAL), dataset="GUIDE")], pct0),
        pct0(where_in(rows, "method", ["Decisions + 20 ex."], dataset="GUIDE")[0]["noise_reduction"])))
add("Noise reduction: production", "78--82\\% of non-malicious production alerts against 69\\%", NOISE, None,
    lambda rows: "{}\\% of non-malicious production alerts against {}\\%".format(
        rng([float(r["noise_reduction"]) for r in where_in(rows, "method", PROD_LOCAL, dataset="production")], pct0),
        pct0(where_in(rows, "method", ["Decisions + exemplar"], dataset="production")[0]["noise_reduction"])))
add("Noise reduction: GUIDE recall", "(.967--.976 against .974)", G80, None,
    lambda rows: "({} against {})".format(
        rng([int(r["TP"]) / (int(r["TP"]) + int(r["FN"])) for r in where_in(rows, "method", TOP3)], p3),
        rec(where_in(rows, "method", ["Decisions + 20 ex."])[0])))
add("Confidence ranking: RiskFit per tenant",
    "from 91.0\\% to 96.1\\% on tenant A, from 75.1\\% to 79.7\\% on tenant B and from 95.4\\% to 99.7\\% on tenant C", RANK, None,
    lambda rows: "from {} to {} on tenant A, from {} to {} on tenant B and from {} to {} on tenant C".format(
        *[pct1(r[k]) for r in where_in(rows, "method", ["RiskFit"]) for k in ("accuracy_automated_at_100", "accuracy_automated_at_80")]))
add("Confidence ranking: Gemini tenant B", "(51.3\\% at full coverage, 50.5\\% at 80\\%)", RANK,
    {"method": "Gemini + exemplar", "tenant": "B"},
    lambda r: f"({pct1(r['accuracy_automated_at_100'])} at full coverage, {pct1(r['accuracy_automated_at_80'])} at 80\\%)")
for m, v in (("RiskFit", "14"), ("CE", "16"), ("MaxSim", "21")):
    add(f"Weighted cost: production crossover {m}", f"above about {v}", "data:one_to_one_vs_decisions_exemplar.csv",
        {"gate": "test-quantile 80%", "condition": "unperturbed", "method": m, "versus": "Decisions + exemplar"},
        lambda r: f"above about {i(r['c_star_point'])}")
add("Weighted cost: MaxSim crossover interval", "11--71", "data:one_to_one_vs_decisions_exemplar.csv",
    {"gate": "test-quantile 80%", "condition": "unperturbed", "method": "MaxSim", "versus": "Decisions + exemplar"},
    lambda r: f"{i(r['c_star_boot_p2.5'])}--{i(r['c_star_boot_p97.5'])}")


def _dominates(rows, a, b):
    ra, rb = (where_in(rows, "method", [m])[0] for m in (a, b))
    return int(ra["misses"]) <= int(rb["misses"]) and int(ra["false_esc"]) < int(rb["false_esc"])


add("Weighted cost: GUIDE dominance", "RiskFit and Tiny Decision have no more misses and fewer false escalations", G80, None,
    lambda rows: "RiskFit and Tiny Decision have no more misses and fewer false escalations"
    if all(_dominates(rows, m, "Decisions + 20 ex.") for m in ("RiskFit", "Tiny Decision")) else "not dominated")
add("Weighted cost: GUIDE CE crossover", "$c\\approx18$", G80, None,
    lambda rows: "$c\\approx{}$".format(round(
        (int(where_in(rows, "method", ["Decisions + 20 ex."])[0]["false_esc"]) - int(where_in(rows, "method", ["CE"])[0]["false_esc"]))
        / (int(where_in(rows, "method", ["CE"])[0]["misses"]) - int(where_in(rows, "method", ["Decisions + 20 ex."])[0]["misses"])))))

# ----------------------------------------------------------------------------------------------- automation sweep (Figure 1)
add("Sweep: hosted <=1 ex. and Jev + 20 ex. FE floor", "made at least 120 false escalations", SWEEP, None,
    lambda rows: "made at least 120 false escalations"
    if min(int(r["false_esc"]) for r in where_in(rows, "method", HOSTED_01 + ["Jev + 20 ex."])) >= 120 else "below 120")
add("Sweep: D20 FE range", "Decisions with 20 exemplars made 48 to 126", SWEEP, None,
    lambda rows: "Decisions with 20 exemplars made " + rng([int(r["false_esc"]) for r in where_in(rows, "method", ["Decisions + 20 ex."])], sep=" to "))
add("Sweep: local FE range", "the three local classifiers made 5 to 79", SWEEP, None,
    lambda rows: "the three local classifiers made " + rng([int(r["false_esc"]) for r in where_in(rows, "method", TOP3)], sep=" to "))
add("Sweep: misses at 90%", "(at 90\\%: 12 and 14 against 16 to 22)", SWEEP, None,
    lambda rows: "(at 90\\%: {} and {} against {})".format(
        where_in(rows, "method", ["Decisions + 1 ex."], target_coverage="0.9000")[0]["misses"],
        where_in(rows, "method", ["Decisions + 20 ex."], target_coverage="0.9000")[0]["misses"],
        rng([int(r["misses"]) for r in where_in(rows, "method", TOP3, target_coverage="0.9000")], sep=" to ")))
for m, a, b in (("RiskFit", "25", "79"), ("CE", "27", "70"), ("Tiny Decision", "33", "50"),
                ("Decisions + 20 ex.", "22", "126"), ("Decisions + 1 ex.", "24", "500")):
    add(f"Sweep: full coverage {m}", f"{a} with {b}", SWEEP, {"method": m, "target_coverage": "1.0000"},
        lambda r: f"{i(r['misses'])} with {i(r['false_esc'])}")
add("Production full coverage: Decisions + ex.", "2 of 73 with 213", PF, {"method": "Decisions + exemplar", "scope": "all"},
    lambda r: f"{i(r['misses'])} of {r['n_mal']} with {i(r['false_esc'])}")
add("Production full coverage: RiskFit", "17 with 64", PF, {"method": "RiskFit", "scope": "all"},
    lambda r: f"{i(r['misses'])} with {i(r['false_esc'])}")
add("Production full coverage: CE", "CE 22 with 36", PF, {"method": "CE", "scope": "all"},
    lambda r: f"CE {i(r['misses'])} with {i(r['false_esc'])}")

# ----------------------------------------------------------------------------------------------- Table 3 and its text
for m, vals in {"RiskFit": ("79.3\\%", "12", "47", ".904", ".974"), "CE": ("80.2\\%", "15", "33", ".930", ".967"),
                "Tiny Decision": ("80.4\\%", "13", "33", ".931", ".971"),
                "Decisions + 1 ex.": ("81.0\\%", "10", "416", ".517", ".978"),
                "Decisions + 20 ex.": ("79.6\\%", "11", "87", ".836", ".976"),
                "Jev + 20 ex.": ("83.5\\%", "31", "223", ".656", ".932")}.items():
    for k, col in enumerate(("automation_rate", "misses", "false_esc", "workflow_precision", "workflow_recall")):
        add(f"Table 3 GUIDE {m} {col}", vals[k], GDEP, {"method": m}, lambda r, c=col: EXACT[c](r) if c in EXACT else i(r[c]))
for m, vals in {"RiskFit": ("74.5\\%", "6", "26", ".720", ".918"), "CE": ("77.9\\%", "9", "8", ".889", ".877"),
                "MaxSim": ("78.7\\%", "7", "4", ".943", ".904"), "LightGBM": ("77.5\\%", "14", "4", ".937", ".808"),
                "Decisions + exemplar": ("81.7\\%", "0", "155", ".320", "1.000")}.items():
    for k, col in enumerate(("automation_rate", "misses", "false_esc", "workflow_precision", "workflow_recall")):
        add(f"Table 3 production {m} {col}", vals[k], PD, {"method": m, "scope": "all"},
            lambda r, c=col: EXACT[c](r) if c in EXACT else i(r[c]))
DEPLOYABLE = "deployable (tau at 80% validation coverage)"
for m, vals in {"RiskFit": ("20.1\\%", "2", "0", "1.000", ".818"), "CE": ("15.2\\%", "1", "2", ".833", ".909"),
                "LightGBM": ("71.8\\%", "2", "0", "1.000", ".818"),
                "Decisions + exemplar": ("39.0\\%", "0", "20", ".355", "1.000"),
                "Decisions zero-shot": ("92.8\\%", "0", "268", ".039", "1.000")}.items():
    for k, col in enumerate(("automation_rate", "misses", "false_esc", "workflow_precision", "workflow_recall")):
        add(f"Table 3 later tenant A {m} {col}", vals[k], LATER, {"method": m, "gate": DEPLOYABLE},
            lambda r, c=col: EXACT[c](r) if c in EXACT else i(r[c]))
add("Table 3 text: pooled automation ranges", "(78--84\\% on GUIDE, 74.5--84.5\\% on production)", GDEP, None,
    lambda rows: "({}\\% on GUIDE, {} on production)".format(
        rng([float(r["automation_rate"]) for r in rows if r["automation_rate"]], pct0),
        rng([float(r["automation_rate"]) for r in rows_all(PD) if r["scope"] == "all"], lambda x: pct1(x)[:-2]) + "\\%"))
add("Table 3 text: GUIDE organization-level automation", "ranged from 60\\% to 98\\%", GDEP, None,
    lambda rows: "ranged from {}\\% to {}\\%".format(pct0(min(float(r["automation_min_org"]) for r in rows if r["automation_min_org"])),
                                                    pct0(max(float(r["automation_max_org"]) for r in rows if r["automation_max_org"]))))
add("Table 3 text: later alerts automation",
    "15\\% (CE), 20\\% (RiskFit), 39\\% (Decisions + 1 exemplar), 72\\% (LightGBM) and 93\\% (zero-shot Decisions)", LATER, None,
    lambda rows: "{}\\% (CE), {}\\% (RiskFit), {}\\% (Decisions + 1 exemplar), {}\\% (LightGBM) and {}\\% (zero-shot Decisions)".format(
        *[pct0(where_in(rows, "method", [m], gate=DEPLOYABLE)[0]["automation_rate"])
          for m in ("CE", "RiskFit", "Decisions + exemplar", "LightGBM", "Decisions zero-shot")]))
TQ = "test-quantile 80%"
add("Later alerts: RiskFit at 80%", "RiskFit missed 2 of 11 with 1 false escalation", LATER, {"method": "RiskFit", "gate": TQ},
    lambda r: f"RiskFit missed {i(r['misses'])} of {r['n_mal']} with {i(r['false_esc'])} false escalation")
add("Later alerts: LightGBM and CE at 80%", "LightGBM 2 with 0, CE 2 with 28", LATER, None,
    lambda rows: "LightGBM {} with {}, CE {} with {}".format(
        *[where_in(rows, "method", [m], gate=TQ)[0][k] for m in ("LightGBM", "CE") for k in ("misses", "false_esc")]))
add("Later alerts: Decisions + ex. at 80%", "1 with 56", LATER, {"method": "Decisions + exemplar", "gate": TQ},
    lambda r: f"{i(r['misses'])} with {i(r['false_esc'])}")
add("Later alerts: API FE rate on later alerts", "0.18 on the later alerts", "data:later_alerts_tenantA_full_coverage.csv",
    {"method": "Decisions + exemplar"}, lambda r: f"{float(r['mal_fpr']):.2f} on the later alerts")
add("Later alerts: no retrieved exemplar", "66\\% of the later alerts had no retrieved exemplar above the similarity threshold (38\\% before)",
    "data:facts.csv", None,
    lambda rows: "{}\\% of the later alerts had no retrieved exemplar above the similarity threshold ({}\\% before)".format(
        pct0(where_in(rows, "quantity", ["Later tenant A alerts with no exemplar at score >= 0.60 (share)"])[0]["value"]),
        pct0(where_in(rows, "quantity", ["Benchmark tenant A alerts with no exemplar at score >= 0.60 (share)"])[0]["value"])))
add("Later alerts: tenant C export", "RiskFit falsely escalated 295 of 1,034", "data:later_alerts_local_models.csv", None,
    lambda rows: "RiskFit falsely escalated {} of {:,}".format(*(lambda d: (d["false_malicious_verdicts"], d["n"] - d["n_mal"]))(
        {r["metric"]: int(float(r["value"])) for r in rows
         if r["block"] == "full coverage" and r["tenant"] == "C" and r["method"] == "RiskFit"
         and r["metric"] in ("false_malicious_verdicts", "n", "n_mal")})))
known("Later alerts: API FE rate on the benchmark", "0.045 on the benchmark", "data:default_verdicts.csv",
      {"method": "Decisions + exemplar", "scope": "A"},
      lambda r: f"{int(r['false_esc']) / int(r['n_nonmal']):.3f} on the benchmark",
      "tenant A pooled counts give 18/395 = 0.0456 (0.046); no released file holds 0.045 (perhaps a fold mean)")
add("Full automation: Holm p (RiskFit, CE vs D20)", "$p{\\ge}0.39$", GTT, None,
    lambda rows: "$p{{\\ge}}{:.2f}$".format(math.floor(100 * min(
        float(r["p_holm"]) for r in rows if r["target"] == "RiskFit validation FPR (secondary)" and r["hosted"] == "Decisions + 20 ex.")) / 100))
add("Full automation: 5% FPR lowers recall", "a fixed 5\\% validation FPR lowered recall for every method", GTH, None,
    lambda rows: "a fixed 5\\% validation FPR lowered recall for every method" if all(
        int(a["TP"]) < int(b["TP"]) for a in rows if a["target"] == "val FPR 5% (primary)"
        for b in rows if b["target"] == "RiskFit validation FPR (secondary)" and b["method"] == a["method"]) else "not lower for every method")

# ----------------------------------------------------------------------------------------------- sensitivity analyses
for m, v in (("RiskFit", "83.6\\% for RiskFit"), ("CE", "72.7\\% for CE"), ("Decisions + 20 ex.", "68.0\\% for Decisions + 20 exemplars")):
    add(f"Incident weighting: automated incidents {m}", v, IW, {"method": m, "coverage": "0.8000"},
        lambda r, v=v: f"{pct1(r['incident_automation_rate'])} for {v.split(' for ')[1]}")
add("Incident weighting: RiskFit missed", "26 of 4,259", IW, {"method": "RiskFit", "coverage": "0.8000"},
    lambda r: f"{i(r['missed_mal_incidents'])} of {int(r['mal_incidents']):,}")
add("Incident weighting: CE missed", "and CE 30", IW, {"method": "CE", "coverage": "0.8000"},
    lambda r: f"and CE {i(r['missed_mal_incidents'])}")
add("Incident weighting: D20 missed", "535", IW, {"method": "Decisions + 20 ex.", "coverage": "0.8000"},
    lambda r: i(r["missed_mal_incidents"]))
add("Incident weighting: D20 single prompt", "508", IC,
    {"quantity": "Decisions + 20 ex.: malicious incidents missed via its single largest prompt"}, lambda r: i(r["value"]))
add("Incident weighting: D20 FE", "188 of 5,463", IW, {"method": "Decisions + 20 ex.", "coverage": "0.8000"},
    lambda r: f"{i(r['false_esc_incidents'])} of {int(r['nonmal_incidents']):,}")
add("Incident weighting: RiskFit FE", "581 for RiskFit", IW, {"method": "RiskFit", "coverage": "0.8000"},
    lambda r: f"{i(r['false_esc_incidents'])} for RiskFit")
add("Incident weighting: CE FE", "363 for CE", IW, {"method": "CE", "coverage": "0.8000"},
    lambda r: f"{i(r['false_esc_incidents'])} for CE")
add("Incident weighting: largest prompt", "anywhere from one to 1,317", IC, {"quantity": "largest test prompt (incidents)"},
    lambda r: f"anywhere from one to {int(r['value']):,}")
NDUP = {"subset": "non-duplicate: max cos < 0.95"}
add("Duplicates: subset size", "280 test alerts with no training neighbor above cosine similarity 0.95 (37 malicious)",
    "data:non_duplicate_subset.csv", {**NDUP, "method": "RiskFit"},
    lambda r: f"{r['n_alerts']} test alerts with no training neighbor above cosine similarity 0.95 ({r['n_mal']} malicious)")
for m, pre, mid in (("RiskFit", "RiskFit made ", " misses"), ("CE", "CE ", ""), ("Tiny Decision", "Tiny Decision ", ""),
                    ("Decisions + exemplar", "one exemplar ", "")):
    add(f"Duplicates: {m} at the gate", None, "data:non_duplicate_subset.csv", {**NDUP, "method": m},
        lambda r, pre=pre, mid=mid: f"{pre}{i(r['gate80_unreviewed_misses'])}{mid} with {i(r['gate80_false_escalations'])}")
for m, v in (("RiskFit", "9 to 8"), ("CE", "9 to 10"), ("kNN (frozen)", "16 to 18"), ("Decisions + exemplar", "0 to 2")):
    add(f"Response field removed: {m}", v, "data:evasion.csv", None,
        lambda rows, m=m: "{} to {}".format(*[where_in(rows, "method", [m], gate="test-quantile 80%", condition=c)[0]["unreviewed_misses"]
                                              for c in ("none", "R0")]))

# ----------------------------------------------------------------------------------------------- Table 4 and hinge text
for (sm, loss), (c, cs, fe, fes) in {("balanced", "CE"): ("47.3", "2.5", "27.0", "6.6"),
                                     ("balanced", "rho=0.9 lambda=2"): ("49.3", "3.5", "31.3", "4.7"),
                                     ("natural", "CE"): ("11.7", "0.6", "1.7", "1.5"),
                                     ("natural", "rho=0.9 lambda=2"): ("46.0", "4.0", "30.3", "13.1")}.items():
    flt = {"sampling": sm, "loss": loss}
    add(f"Table 4 {sm} {loss} caught", pm(c, cs), HINGE, flt, lambda r: pm(f1(r["caught_mean"]), f1(r["caught_sd_across_seeds"])))
    add(f"Table 4 {sm} {loss} FE", pm(fe, fes), HINGE, flt, lambda r: pm(f1(r["fe_mean"]), f1(r["fe_sd_across_seeds"])))
add("Hinge: natural-sampling seeds", "46, 50, 42", HINGE, {"sampling": "natural", "loss": "rho=0.9 lambda=2"},
    lambda r: r["caught_per_seed_units"].replace("/", ", "))
add("Hinge: stronger arm rho .95", "45.3", HINGE, {"sampling": "natural", "loss": "rho=0.95 lambda=5"}, lambda r: f1(r["caught_mean"]))
add("Hinge: stronger arm rho .99", "47.0", HINGE, {"sampling": "natural", "loss": "rho=0.99 lambda=8"}, lambda r: f1(r["caught_mean"]))
add("Hinge: additional FE", "approximately 28.7 additional false escalations", HINGE, None,
    lambda rows: "approximately {} additional false escalations".format(f1(
        float(where_in(rows, "loss", ["rho=0.9 lambda=2"], sampling="natural")[0]["fe_mean"])
        - float(where_in(rows, "loss", ["CE"], sampling="natural")[0]["fe_mean"]))))
add("Hinge: training soft recall under balanced CE", "from 0.36 to 0.99", "data:hinge_by_sampling_activity.csv",
    {"sampling": "balanced", "loss": "CE"},
    lambda r: f"from {float(r['mean_softrec_ep1_mean']):.2f} to {float(r['mean_softrec_last_mean']):.2f}")
add("Hinge: recall target sweep", "test recall 0.72--0.74", "data:recall_target_sweep_monotonicity.csv", None,
    lambda rows: "test recall " + rng([float(rows[0][f"mean_R_rho{r}"]) for r in ("0.7", "0.8", "0.9", "0.95")], lambda x: f"{x:.2f}"))
add("Hinge: seven seeds RiskFit - CE", "RiskFit caught 0.6 more malicious alerts than CE on average and made 9 more false escalations",
    "data:seeds_riskfit_vs_ce_7seeds_tests.csv", None,
    lambda rows: "RiskFit caught {} more malicious alerts than CE on average and made {} more false escalations".format(
        f1(where_in(rows, "metric", ["caught"])[0]["pooled_diff"]), i(where_in(rows, "metric", ["fe"])[0]["pooled_diff"])))

# ----------------------------------------------------------------------------------------------- limitations, reproducibility
add("Limitations: small validation sets", "only 3, 4, 13 and 17 non-malicious validation prompts", TASK, None,
    lambda rows: "only {}, {}, {} and {} non-malicious validation prompts".format(*sorted(
        int(r["prompts"]) - int(r["mal_prompts"]) for r in rows if r["level"] == "org" and r["split"] == "val")[:4]))
add("Limitations: malicious test prompts in those orgs", "they hold 287 of the 456 malicious test prompts", TASK, None,
    lambda rows: (lambda small: "they hold {} of the {} malicious test prompts".format(
        sum(int(r["mal_prompts"]) for r in rows if r["level"] == "org" and r["split"] == "test" and r["org"] in small),
        sum(int(r["mal_prompts"]) for r in rows if r["level"] == "org" and r["split"] == "test")))(
        {r["org"] for r in sorted((r for r in rows if r["level"] == "org" and r["split"] == "val"),
                                  key=lambda r: int(r["prompts"]) - int(r["mal_prompts"]))[:4]}))
add("Reproducibility: Decisions repeat calls", "3,300 repeated production calls", "data:facts.csv",
    {"quantity": "Decisions API repeat calls (production)"}, lambda r: f"{int(float(r['value'])):,} repeated production calls")


# ----------------------------------------------------------------------------------------------- runner
_CACHE: dict[str, list[dict]] = {}
_INP: Inputs | None = None


def _path(source: str) -> Path:
    if source.startswith("data:"):
        return _INP.production / source[5:]
    return _INP.out / source


def rows_all(source: str) -> list[dict]:
    if source not in _CACHE:
        _CACHE[source] = read_csv(_path(source))
    return _CACHE[source]


def rows_of(source: str, match: dict) -> dict:
    for r in rows_all(source):
        if all(r.get(k) == v for k, v in match.items()):
            return r
    raise KeyError(f"{source}: no row {match}")


def evaluate(c: Claim, tex: str):
    try:
        got = c.fn(rows_of(c.source, c.match) if c.match is not None else rows_all(c.source))
    except Exception as e:  # noqa: BLE001 -- report, do not crash the whole check
        got = f"ERROR {type(e).__name__}: {e}"
    printed = got if c.printed is None else c.printed
    return printed, got, got == printed, printed in tex


def check(inp: Inputs, tex_path: Path) -> int:
    global _INP
    _INP = inp
    _CACHE.clear()
    tex = Path(tex_path).read_text(encoding="utf-8")
    out, failed = [], 0
    for c in CLAIMS:
        printed, got, ok, in_tex = evaluate(c, tex)
        out.append({"claim": c.where, "printed": printed, "computed": got, "source": c.source,
                    "row": "; ".join(f"{k}={v}" for k, v in (c.match or {}).items()),
                    "status": "ok" if ok and in_tex else "FAIL", "found_in_tex": in_tex})
        if not (ok and in_tex):
            failed += 1
            print(f"  FAIL {c.where}: printed={printed!r} computed={got!r} in_tex={in_tex}")
    for c, note in KNOWN_ISSUES:
        printed, got, ok, in_tex = evaluate(c, tex)
        out.append({"claim": c.where, "printed": printed, "computed": got, "source": c.source,
                    "row": "; ".join(f"{k}={v}" for k, v in (c.match or {}).items()),
                    "status": "ok" if ok and in_tex else "known issue: " + note, "found_in_tex": in_tex})
        if not ok:
            print(f"  KNOWN ISSUE {c.where}: printed {printed!r}, data give {got!r} ({note})")
    path = inp.out / "claims_check.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"  {len(CLAIMS) - failed} of {len(CLAIMS)} printed numbers verified; {len(KNOWN_ISSUES)} known issue(s) listed in "
          f"{path.name}")
    return failed
