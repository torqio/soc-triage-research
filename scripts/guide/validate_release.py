#!/usr/bin/env python3
"""Validate the released GUIDE results against splits rebuilt from the public GUIDE dataset.

Run after scripts/guide/build_splits.py. No model is trained or called. Checks:
  1. the incident -> prompt -> split membership rebuilt from GUIDE is byte-identical to the released
     data/guide/prompt_membership.csv (which the incident-weighting analysis reads);
  2. every prompt id re-derives from its rendered text: guide-<org>-p<sha256(text)[:16]>;
  3. every released per-prompt file (6 local models, 7 hosted / open-LLM files) covers exactly the rebuilt
     validation and test prompts of each organization, with the same labels (Opus: test prompts only);
  4. every exemplar id in the released hosted outputs is a training prompt of the same organization.
Exit status 0 only if every check passes.

Usage: python scripts/guide/validate_release.py [--build-dir work/guide]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from soctriage import guide as G  # noqa: E402
from soctriage import paths  # noqa: E402
from soctriage.serialization import render_alert  # noqa: E402

HOSTED_LABEL = {"malicious": "True Positive - Malicious", "benign": "True Positive - Benign",
                "false_positive": "False Positive"}
# released hosted / open-LLM files: (file, prompt-id column, label column, has validation rows, exemplar-id columns)
HOSTED_FILES = [
    ("decisions_guide_per_prompt.csv", "prompt_id", "label", True, ["exemplar_prompt_id"]),
    ("jev_guide_per_prompt.csv", "prompt_id", "label", True, ["exemplar_prompt_id"]),
    ("decisions_jev_5ex_guide_per_prompt.csv", "prompt_id", "label", True, [f"ex{j}_prompt_id" for j in range(1, 6)]),
    ("decisions_jev_20ex_guide_per_prompt.csv", "prompt_id", "label", True, [f"ex{j}_prompt_id" for j in range(1, 21)]),
    ("opus_guide_per_prompt.csv", "prompt_id", "label", False, []),
    ("cybersecqwen4b_zeroshot_guide_per_prompt.csv", "id", "y", True, []),
    ("qwen3_4b_base_zeroshot_guide_per_prompt.csv", "id", "y", True, []),
]


class Report:
    def __init__(self):
        self.failed = 0

    def check(self, ok: bool, what: str, detail: str = "") -> bool:
        print(f"[{'PASS' if ok else 'FAIL'}] {what}{(': ' + detail) if detail else ''}", flush=True)
        self.failed += not ok
        return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", type=Path, default=paths.WORK / "guide",
                    help="the --out directory of scripts/guide/build_splits.py (default: work/guide)")
    a = ap.parse_args()
    rep = Report()
    orgs = [r["org_id"] for r in G.iter_orgs(paths.GUIDE_ORGS)]

    # 1. membership table
    rebuilt = a.build_dir / "guide_prompt_membership.csv"
    if not rebuilt.exists():
        print(f"{rebuilt} not found: run scripts/guide/build_splits.py first")
        return 1
    rep.check(rebuilt.read_bytes() == paths.GUIDE_MEMBERSHIP.read_bytes(),
              "released data/guide/prompt_membership.csv is byte-identical to the one rebuilt from GUIDE",
              f"sha256 {hashlib.sha256(rebuilt.read_bytes()).hexdigest()[:16]}...")

    # 2. splits, and prompt ids derived from the rendered text
    splits = {o: G.load_split(a.build_dir / "splits", o) for o in orgs}  # verifies each file against its manifest
    bad_ids = [r["alert_id"] for o in orgs for s in splits[o].values() for r in s
               if r["alert_id"] != f"guide-{o}-p{hashlib.sha256(render_alert(r).encode()).hexdigest()[:16]}"]
    n_prompts = sum(len(v) for o in orgs for v in splits[o].values())
    rep.check(not bad_ids, f"all {n_prompts:,} prompt ids re-derive from their rendered text", f"{len(bad_ids)} differ")

    want = {(o, s): {(r["alert_id"], r["label"]) for r in splits[o][s]} for o in orgs for s in ("val", "test")}
    train_ids = {o: {r["alert_id"] for r in splits[o]["train"]} for o in orgs}

    # 3a. local-model predictions
    for d in sorted(p for p in paths.GUIDE_PREDICTIONS.iterdir() if p.is_dir()):
        got = defaultdict(set)
        for o in orgs:
            for line in (d / f"org_{o}.jsonl").open():
                if line.strip():
                    r = json.loads(line)
                    got[(o, r["split"])].add((r["alert_id"], r["expected_label"]))
        bad = [k for k in want if got[k] != want[k]]
        rep.check(not bad and set(got) == set(want), f"local predictions {d.name}: prompts and labels match the rebuilt splits",
                  f"{sum(len(v) for v in got.values())} rows" + (f"; mismatches in {bad[:3]}" if bad else ""))

    # 3b + 4. hosted and open-LLM outputs
    for fname, id_col, lab_col, has_val, ex_cols in HOSTED_FILES:
        rows = list(csv.DictReader((paths.GUIDE_HOSTED / fname).open(newline="")))
        got = defaultdict(set)
        bad_ex = 0
        for r in rows:
            org = r["org"]
            split = r.get("split", "test")
            got[(org, split)].add((r[id_col], HOSTED_LABEL[r[lab_col]]))
            bad_ex += sum(bool(r[c]) and r[c] not in train_ids[org] for c in ex_cols)
        keys = [k for k in want if has_val or k[1] == "test"]
        bad = [k for k in keys if got.get(k) != want[k]]
        rep.check(not bad and set(got) == set(keys), f"{fname}: prompts and labels match the rebuilt splits",
                  f"{len(rows)} rows" + (f"; mismatches in {bad[:3]}" if bad else ""))
        if ex_cols:
            n_ex = sum(bool(r[c]) for r in rows for c in ex_cols)
            rep.check(bad_ex == 0, f"{fname}: every exemplar is a training prompt of the same organization",
                      f"{n_ex:,} exemplar ids, {bad_ex} not in training")

    print("ALL CHECKS PASSED" if rep.failed == 0 else f"{rep.failed} CHECK(S) FAILED", flush=True)
    return 0 if rep.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
