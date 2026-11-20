"""Score retrained GUIDE predictions against the paper's released ones (Tables 2 and 3, GUIDE blocks).

  python -m soctriage.analysis compare --predictions work/guide/predictions [--methods riskfit,ce]

The new files must be in the released format (``<method>/org_<id>.jsonl`` written by scripts/guide/train.py)
and cover the same validation and test prompts with the same labels. For each method the report shows the
paper's and the new 80%-gate misses / false escalations / workflow precision and recall, the 100% numbers,
the validation-threshold gate, and how many test verdicts agree with the released predictions. Retraining on
other hardware or library versions moves individual predictions, so expect small differences in counts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import paths
from .data import load_guide
from .gates import counts, gate_quantile, gate_tau, pooled, tau_validation, workflow
from .io import write_csv
from .methods import LOCAL

BY_DIR = {d: m for m, d in LOCAL.items()}


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--predictions", type=Path, required=True, help="directory with <method>/org_<id>.jsonl")
    p.add_argument("--methods", help="comma-separated method directories (default: every one found)")
    p.add_argument("--report", type=Path, default=paths.WORK / "guide" / "compare_to_paper.csv")


def _metrics(orgs, data, m):
    g80 = workflow(pooled([counts(data[(m, o)]["test"], gate_quantile(data[(m, o)]["test"], 0.8)) for o in orgs]))
    g100 = workflow(pooled([counts(data[(m, o)]["test"], gate_quantile(data[(m, o)]["test"], 1.0)) for o in orgs]))
    dep = workflow(pooled([counts(data[(m, o)]["test"], gate_tau(data[(m, o)]["test"], tau_validation(data[(m, o)]["val"])))
                           for o in orgs]))
    return {"gate80_misses": g80["misses"], "gate80_fe": g80["false_esc"],
            "gate80_wprec": g80["workflow_precision"], "gate80_wrec": g80["workflow_recall"],
            "full_misses": g100["misses"], "full_fe": g100["false_esc"],
            "val_gate_automation": dep["automation_rate"], "val_gate_misses": dep["misses"], "val_gate_fe": dep["false_esc"]}


def main(a) -> int:
    pred = Path(a.predictions)
    dirs = a.methods.split(",") if a.methods else sorted(p.name for p in pred.iterdir() if p.is_dir() and p.name in BY_DIR)
    unknown = [d for d in dirs if d not in BY_DIR]
    if unknown or not dirs:
        raise SystemExit(f"no known method directories in {pred} (expected some of {sorted(BY_DIR)}; got {dirs})")
    names = [BY_DIR[d] for d in dirs]
    orgs_new, new = load_guide(pred, local_methods=names, with_hosted=False)
    orgs_ref, ref = load_guide(paths.GUIDE_PREDICTIONS, local_methods=names, with_hosted=False, orgs=orgs_new)
    if len(orgs_new) < 12:
        print(f"partial run: organizations {', '.join(orgs_new)} only (the paper pools 12)")
    for m in names:  # same prompts and labels as the paper's run
        for o in orgs_ref:
            for s in ("test", "val"):
                a_ids = {(r["id"], r["y"]) for r in new[(m, o)][s]}
                b_ids = {(r["id"], r["y"]) for r in ref[(m, o)][s]}
                if a_ids != b_ids:
                    raise SystemExit(f"{m} org {o} {s}: prompts or labels differ from the released predictions "
                                     "(were the splits rebuilt with scripts/guide/build_splits.py?)")
    rows = []
    hdr = f"{'method':14s} {'':6s} {'80% miss':>8s} {'FE':>5s} {'W.prec':>7s} {'W.rec':>6s} {'100% miss':>9s} {'FE':>5s} {'val-gate auto':>13s} {'miss':>5s} {'FE':>5s}"
    print(hdr)
    for m in names:
        paper, now = _metrics(orgs_ref, ref, m), _metrics(orgs_ref, new, m)
        agree = sum(a["pred"] == b["pred"] for o in orgs_ref for a, b in zip(
            sorted(ref[(m, o)]["test"], key=lambda r: r["id"]), sorted(new[(m, o)]["test"], key=lambda r: r["id"])))
        n_test = sum(len(ref[(m, o)]["test"]) for o in orgs_ref)
        for label, v in (("paper", paper), ("rerun", now)):
            print(f"{m if label == 'paper' else '':14s} {label:6s} {v['gate80_misses']:8d} {v['gate80_fe']:5d} {v['gate80_wprec']:7.3f} "
                  f"{v['gate80_wrec']:6.3f} {v['full_misses']:9d} {v['full_fe']:5d} {v['val_gate_automation']:13.1%} "
                  f"{v['val_gate_misses']:5d} {v['val_gate_fe']:5d}")
            rows.append({"method": m, "source": label, **v})
        print(f"{'':14s} {'':6s} test verdicts equal to the paper's: {agree}/{n_test} ({agree / n_test:.1%})")
        rows[-1]["test_verdict_agreement"] = agree / n_test
    write_csv(a.report, rows)
    print(f"wrote {a.report}")
    return 0
