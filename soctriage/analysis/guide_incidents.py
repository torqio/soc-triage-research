"""What the GUIDE-derived task is, and the incident-weighted sensitivity analysis.

Reads the public incident -> prompt -> split membership (data/guide/prompt_membership.csv).
Outputs (outputs/guide/):
  task_label_conflicts.csv     incidents, prompts, mixed-label prompts, ties and conflicting labels per org x split
  incident_weighted.csv        every test incident inherits its prompt's gate decision and verdict (80% and 100%);
                               also the share of incidents automated (methods automate different prompts)
  incident_concentration.csv   how concentrated test incidents are across prompts; largest-prompt misses
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .data import Inputs, loaded_methods, read_csv
from .gates import gate_quantile
from .io import write_csv
from .methods import LOCAL_LABEL

WEIGHTED = ["RiskFit", "CE", "Tiny Decision", "kNN", "LightGBM", "MaxSim", "Decisions + 1 ex.", "Decisions + 20 ex.",
            "Jev + 20 ex.", "Opus + 1 ex."]
CONCENTRATION = ["RiskFit", "CE", "Tiny Decision", "Decisions + 1 ex.", "Decisions + 20 ex.", "Jev + 20 ex.",
                 "Opus + 1 ex."]


def load_membership(path):
    """(org, prompt) -> incident labels, split and prompt label."""
    inc = defaultdict(list)
    split_of, plabel = {}, {}
    for r in read_csv(path):
        k = (r["org_id"], r["prompt_id"])
        inc[k].append(LOCAL_LABEL[r["incident_label"]])
        split_of[k] = r["split"]
        plabel[k] = LOCAL_LABEL[r["prompt_label"]]
    return inc, split_of, plabel


def run(inp: Inputs) -> None:
    inc, split_of, plabel = load_membership(inp.membership)
    orgs, data = inp.guide()
    methods = loaded_methods(data)
    out = inp.out / "guide"

    # the membership table agrees with the prediction files (same prompts, splits and labels)
    ref = methods[0]
    for o in orgs:
        for s in ("test", "val"):
            for r in data[(ref, o)][s]:
                k = (o, r["id"])
                assert split_of[k] == s and plabel[k] == r["y"], f"membership disagrees with predictions: {k}"

    agg = defaultdict(Counter)
    for k, labs in inc.items():
        o, s = k[0], split_of[k]
        c = Counter(labs)
        top = c.most_common()
        tie = len(top) > 1 and top[0][1] == top[1][1]
        for key in (("org", o, s), ("all", "all", s), ("all", "all", "all")):
            a = agg[key]
            a["prompts"] += 1
            a["incidents"] += len(labs)
            a["mixed_prompts"] += len(c) > 1
            a["tied_prompts"] += tie
            a["conflicting_incidents"] += sum(1 for x in labs if x != plabel[k])
            a["mal_prompts"] += plabel[k] == "mal"
            a["mal_incidents"] += sum(x == "mal" for x in labs)
            a["prompts_singleton"] += len(labs) == 1
            a["mal_incidents_in_nonmal_prompts"] += sum(x == "mal" for x in labs) if plabel[k] != "mal" else 0
            a["nonmal_incidents_in_mal_prompts"] += sum(x != "mal" for x in labs) if plabel[k] == "mal" else 0
    write_csv(out / "task_label_conflicts.csv", [
        {"level": lvl, "org": o, "split": s, **a, "incidents_per_prompt": a["incidents"] / a["prompts"],
         "conflicting_incident_share": a["conflicting_incidents"] / a["incidents"],
         "mixed_prompt_share": a["mixed_prompts"] / a["prompts"]}
        for (lvl, o, s), a in sorted(agg.items())])

    weighted = []
    for m in (m for m in WEIGHTED if m in methods):
        for cov in (0.8, 1.0):
            miss = fe = n_mal = n_non = auto_inc = 0
            for o in orgs:
                test = data[(m, o)]["test"]
                kept = gate_quantile(test, cov)
                for r in test:
                    auto = r["id"] in kept
                    auto_inc += auto * len(inc[(o, r["id"])])
                    for x in inc[(o, r["id"])]:
                        if x == "mal":
                            n_mal += 1
                            miss += auto and r["pred"] != "mal"
                        else:
                            n_non += 1
                            fe += auto and r["pred"] == "mal"
            weighted.append({"method": m, "coverage": cov, "mal_incidents": n_mal, "nonmal_incidents": n_non,
                             "missed_mal_incidents": miss, "false_esc_incidents": fe,
                             "incident_workflow_recall": 1 - miss / n_mal,
                             "incident_workflow_precision": (n_mal - miss) / (n_mal - miss + fe),
                             "automated_incidents": auto_inc, "incident_automation_rate": auto_inc / (n_mal + n_non)})
    write_csv(out / "incident_weighted.csv", weighted)

    sizes = sorted((len(inc[(o, r["id"])]) for o in orgs for r in data[(ref, o)]["test"]), reverse=True)
    total = sum(sizes)
    rows = [{"quantity": "test prompts", "value": len(sizes)},
            {"quantity": "test incidents", "value": total},
            {"quantity": "test prompts with one incident", "value": sum(s == 1 for s in sizes)},
            {"quantity": "largest test prompt (incidents)", "value": sizes[0]},
            {"quantity": "share of test incidents in the 11 largest test prompts (1%)", "value": sum(sizes[:11]) / total}]
    for m in (m for m in CONCENTRATION if m in methods):
        missed = []
        for o in orgs:
            kept = gate_quantile(data[(m, o)]["test"], 0.8)
            for r in data[(m, o)]["test"]:
                n = sum(x == "mal" for x in inc[(o, r["id"])])
                if r["id"] in kept and r["pred"] != "mal" and n:
                    missed.append(n)
        missed.sort(reverse=True)
        rows += [{"quantity": f"{m}: automated non-malicious-verdict prompts holding malicious incidents", "value": len(missed)},
                 {"quantity": f"{m}: malicious incidents missed at 80%", "value": sum(missed)},
                 {"quantity": f"{m}: malicious incidents missed via its single largest prompt", "value": missed[0] if missed else 0}]
    write_csv(out / "incident_concentration.csv", rows)
