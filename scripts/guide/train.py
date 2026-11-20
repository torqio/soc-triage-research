#!/usr/bin/env python3
"""Train a local model per GUIDE organization and write per-prompt validation/test predictions.

For each organization: load the verified split files, render every prompt with the 21-field serializer
(LightGBM reads the structured record instead), fit on train with early stopping on validation, and write
predictions/<method>/org_<id>.jsonl with one line per prompt:
  {"alert_id", "split", "expected_label", "predicted_label", "confidence", "class_probs"}
(confidence = max class probability; class_probs rounded to 6 decimals). These files are what
`python -m soctriage.analysis compare` reads.

Usage:
  python scripts/guide/train.py --splits work/guide/splits --method riskfit --out work/guide/predictions
  python scripts/guide/train.py ... --method ce
  python scripts/guide/train.py ... --method lightgbm
  python scripts/guide/train.py ... --method maxsim          # configs/guide/models/maxsim.yaml
  python scripts/guide/train.py ... --method knn             # configs/guide/models/knn.yaml (CPU is enough)
  python scripts/guide/train.py ... --method tiny_decision   # Qwen3-0.6B-LoRA, configs/guide/models/tiny_decision.yaml
  # any recipe: --config configs/production/<recipe>.yaml --method <name>
  # smoke run: --orgs 78 --max-train 24 --max-eval 16 --epochs 1
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from soctriage import guide as G  # noqa: E402
from soctriage.models import TEXT_INPUT, build_model  # noqa: E402
from soctriage.serialization import render_alert  # noqa: E402

METHODS = ("riskfit", "ce", "lightgbm", "maxsim", "knn", "tiny_decision")  # configs/guide/models/<method>.yaml


def label_weighting(records, gold_weight=2.0, silver_weight=1.0):
    """Oversample analyst-corrected ('gold') records; used by the production recipes (apply_weighting: true)."""
    out = []
    for r in records:
        reps = {"gold": round(gold_weight), "silver": round(silver_weight)}.get(r.get("label_source"), 1)
        out += [copy.deepcopy(r) for _ in range(reps)]
    return out


def subsample(recs, n, seed=0):
    """Stratified tiny subset for smoke runs (keeps at least one prompt of each label when possible)."""
    if not n or n >= len(recs):
        return recs
    rng = random.Random(seed)
    by = {}
    for r in recs:
        by.setdefault(r["label"], []).append(r)
    out = [rng.choice(v) for v in by.values()][:n]
    rest = [r for r in recs if r not in out]
    out += rng.sample(rest, n - len(out))
    return sorted(out, key=lambda r: r["alert_id"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", type=Path, default=ROOT / "work" / "guide" / "splits",
                    help="the splits/ directory written by scripts/guide/build_splits.py (default: work/guide/splits)")
    ap.add_argument("--method", required=True, help="output name (riskfit, ce, lightgbm, maxsim, knn, tiny_decision, or any label)")
    ap.add_argument("--config", type=Path, help="model recipe YAML (default: configs/guide/models/<method>.yaml)")
    ap.add_argument("--out", type=Path, default=ROOT / "work" / "guide" / "predictions",
                    help="writes <out>/<method>/org_<id>.jsonl (default: work/guide/predictions)")
    ap.add_argument("--orgs", help="comma-separated organizations (default: all 12)")
    ap.add_argument("--epochs", type=int, help="override num_train_epochs (smoke runs)")
    ap.add_argument("--max-train", type=int, help="smoke runs: stratified subset of the training split")
    ap.add_argument("--max-eval", type=int, help="smoke runs: subset of validation and test")
    ap.add_argument("--seed", type=int, help="override the recipe's training seed")
    a = ap.parse_args()

    cfg_path = a.config or ROOT / "configs" / "guide" / "models" / f"{a.method}.yaml"
    if not cfg_path.exists():
        ap.error(f"no recipe {cfg_path}; use one of {', '.join(METHODS)} or pass --config")
    recipe = yaml.safe_load(cfg_path.read_text())
    if a.epochs is not None:
        recipe["num_train_epochs"] = a.epochs
    if a.seed is not None:
        recipe["seed"] = a.seed
    orgs = a.orgs.split(",") if a.orgs else [r["org_id"] for r in G.iter_orgs(ROOT / "configs" / "guide" / "organizations.csv")]
    kw = recipe.get("preprocessor_kwargs") or {}
    out_dir = a.out / a.method
    out_dir.mkdir(parents=True, exist_ok=True)
    for org in orgs:
        t0 = time.time()
        sp = G.load_split(a.splits, org)
        train, val, test = subsample(sp["train"], a.max_train), subsample(sp["val"], a.max_eval), subsample(sp["test"], a.max_eval)
        fit_train, fit_val = train, val
        if kw.get("apply_weighting"):
            fit_train = label_weighting(train, kw.get("gold_weight", 2), kw.get("silver_weight", 1))
            fit_val = label_weighting(val, kw.get("gold_weight", 2), kw.get("silver_weight", 1))
        to_input = render_alert if recipe["model_type"] in TEXT_INPUT else (lambda r: r)
        model = build_model(recipe)
        model.fit([to_input(r) for r in fit_train], [r["label"] for r in fit_train],
                  [to_input(r) for r in fit_val], [r["label"] for r in fit_val])
        classes = [str(c) for c in model.classes_]
        with (out_dir / f"org_{org}.jsonl").open("w") as fh:
            for split, recs in (("val", val), ("test", test)):
                proba = model.predict_proba([to_input(r) for r in recs])
                for r, p in zip(recs, proba):
                    k = int(np.argmax(p))
                    fh.write(json.dumps({"alert_id": r["alert_id"], "split": split, "expected_label": r["label"],
                                         "predicted_label": classes[k], "confidence": float(max(p)),
                                         "class_probs": {c: round(float(x), 6) for c, x in zip(classes, p)}}) + "\n")
        print(f"{a.method} org {org}: trained on {len(fit_train)} prompts in {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
