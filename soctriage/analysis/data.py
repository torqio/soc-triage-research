"""Loaders for the released GUIDE per-prompt files and the production aggregates (standard library only)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import paths
from .methods import (DECISION_FILES, HOSTED_LABEL, LOCAL, LOCAL_LABEL, MAL_LOCAL, METHODS, OPEN, OPUS, OPUS_FILE)


@dataclass
class Inputs:
    """Where the analysis reads from and writes to. Defaults are the released files of this repository."""

    predictions: Path = paths.GUIDE_PREDICTIONS
    hosted: Path = paths.GUIDE_HOSTED
    membership: Path = paths.GUIDE_MEMBERSHIP
    production: Path = paths.PRODUCTION
    out: Path = paths.OUTPUTS
    _guide: tuple | None = field(default=None, repr=False)

    def guide(self):
        """(orgs, data) from :func:`load_guide`, cached."""
        if self._guide is None:
            self._guide = load_guide(self.predictions, self.hosted)
        return self._guide


def fnum(x):
    return None if x in (None, "", "None") else float(x)


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as fh:
        return list(csv.DictReader(fh))


def _local_records(path: Path):
    test, val = [], []
    for line in path.open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["split"] not in ("test", "val"):
            continue
        p = r["class_probs"]
        pred = r["predicted_label"]
        conf = float(p[pred])
        sc = r.get("confidence")
        if sc not in (None, "None") and abs(float(sc) - conf) <= 1e-5:
            conf = float(sc)  # the unrounded max probability, when the file has it
        rec = {"id": r["alert_id"], "y": LOCAL_LABEL[r["expected_label"]], "pred": LOCAL_LABEL[pred],
               "conf": conf, "pmal": float(p.get(MAL_LOCAL, 0.0))}
        (test if r["split"] == "test" else val).append(rec)
    return test, val


def load_guide(pred_dir: Path = paths.GUIDE_PREDICTIONS, hosted_dir: Path = paths.GUIDE_HOSTED,
               local_methods: list[str] | None = None, with_hosted: bool = True, orgs: list[str] | None = None):
    """Load every GUIDE condition.

    Returns ``(orgs, data)`` with ``data[(method, org)] = {"test": [rec], "val": [rec]}`` and
    ``rec = {"id", "y", "pred", "conf", "pmal"}``: label and verdict in {mal, ben, fp, unresolved}, the gate
    confidence, and the score used for full-automation thresholds (p(malicious) for local and open models, the
    predicate probability q2 for Decisions/Jev, the stated p_malicious for Opus). An unresolved hosted call is a
    non-malicious verdict with confidence 0. Opus has test rows only.

    ``local_methods`` restricts the local models (display names); a missing local directory is an error.
    ``orgs`` restricts the organizations (default: every org_<id>.jsonl of the first local model).
    Every loaded condition must cover the same test (and validation) prompts with the same labels.
    """
    pred_dir, hosted_dir = Path(pred_dir), Path(hosted_dir)
    local = {m: LOCAL[m] for m in (local_methods or list(LOCAL))}
    ref_dir = pred_dir / next(iter(local.values()))
    orgs = sorted(orgs or (p.stem.split("_")[1] for p in ref_dir.glob("org_*.jsonl")))
    if not orgs:
        raise FileNotFoundError(f"no org_<id>.jsonl prediction files in {ref_dir}")
    data = {}
    for m, d in local.items():
        for o in orgs:
            test, val = _local_records(pred_dir / d / f"org_{o}.jsonl")
            data[(m, o)] = {"test": test, "val": val}
    if with_hosted:
        for m, fname, pfx in DECISION_FILES:
            for r in read_csv(hosted_dir / fname):
                ok = r[f"{pfx}_verdict"] not in ("", None)
                rec = {"id": r["prompt_id"], "y": HOSTED_LABEL[r["label"]],
                       "pred": HOSTED_LABEL[r[f"{pfx}_verdict"]] if ok else "unresolved",
                       "conf": fnum(r[f"{pfx}_confidence"]) if ok else 0.0,
                       "pmal": (fnum(r[f"{pfx}_p_mal_q2"]) or 0.0) if ok else 0.0}
                if r["org"] in orgs:
                    data.setdefault((m, r["org"]), {"test": [], "val": []})[r["split"]].append(rec)
        opus_name = {cond: name for name, cond in OPUS}
        for r in read_csv(hosted_dir / OPUS_FILE):
            ok = r["verdict"] not in ("", None)
            rec = {"id": r["prompt_id"], "y": HOSTED_LABEL[r["label"]],
                   "pred": HOSTED_LABEL[r["verdict"]] if ok else "unresolved",
                   "conf": float(r["confidence"]) if ok else 0.0, "pmal": float(r["p_malicious"]) if ok else 0.0}
            if r["org"] in orgs:
                data.setdefault((opus_name[r["condition"]], r["org"]), {"test": [], "val": []})["test"].append(rec)
        for m, fname in OPEN:
            for r in read_csv(hosted_dir / fname):
                rec = {"id": r["id"], "y": HOSTED_LABEL[r["y"]], "pred": HOSTED_LABEL[r["verdict"]],
                       "conf": float(r["confidence"]), "pmal": float(r["p_malicious"])}
                if r["org"] in orgs:
                    data.setdefault((m, r["org"]), {"test": [], "val": []})[r["split"]].append(rec)
    _check_same_prompts(orgs, data)
    return orgs, data


def loaded_methods(data) -> list[str]:
    """Loaded conditions in the paper's order."""
    present = {m for m, _ in data}
    return [m for m in METHODS if m in present]


def _check_same_prompts(orgs, data) -> None:
    methods = loaded_methods(data)
    ref = methods[0]
    for o in orgs:
        want_t = {(r["id"], r["y"]) for r in data[(ref, o)]["test"]}
        want_v = {(r["id"], r["y"]) for r in data[(ref, o)]["val"]}
        for m in methods:
            got = {(r["id"], r["y"]) for r in data[(m, o)]["test"]}
            assert got == want_t, f"test prompts or labels of {m} differ from {ref} in org {o}"
            if data[(m, o)]["val"]:
                got = {(r["id"], r["y"]) for r in data[(m, o)]["val"]}
                assert got == want_v, f"validation prompts or labels of {m} differ from {ref} in org {o}"


def has_val(data, m, orgs) -> bool:
    return all(data[(m, o)]["val"] for o in orgs)
