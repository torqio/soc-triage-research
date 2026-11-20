"""Reproduce every number, table and figure of the paper from the released results.

  python -m soctriage.analysis                 run all steps, write outputs/, draw Figure 1, check the paper
  python -m soctriage.analysis --no-figure     skip Figure 1 (no matplotlib needed: standard library only)
  python -m soctriage.analysis --out DIR       write the tables elsewhere (e.g. to diff against outputs/)
  python -m soctriage.analysis compare --predictions DIR [--methods riskfit,ce]
                                               score retrained GUIDE predictions against the paper's (Table 2)

Exit status 1 if a released file fails its integrity check or a number printed in the paper does not match.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .. import paths
from . import claims, compare, figure, guide_gate, guide_incidents, guide_validation, noise_reduction, production
from .data import Inputs


def run_all(inp: Inputs, make_figure: bool = True, check_tex: Path | None = paths.PAPER_TEX,
            figure_dir: Path | None = None) -> int:
    t0 = time.time()
    status = 0
    print(f"inputs: {inp.predictions.parent}, {inp.production}\noutputs: {inp.out}")
    print("[1/7] GUIDE: released per-prompt files reproduce the original 80% gate table ...", end=" ", flush=True)
    ok = guide_gate.released_run_check(inp)
    print("OK" if ok else "FAILED (see guide/released_run_check.csv)")
    status |= not ok
    steps = [("[2/7] GUIDE: fixed review budget, automation sweep, organization tests, bootstrap", guide_gate.run),
             ("[3/7] GUIDE: validation-selected thresholds", guide_validation.run),
             ("[4/7] GUIDE: task diagnostics and incident weighting", guide_incidents.run),
             ("[5/7] production: workflow metrics from aggregates", production.run),
             ("[6/7] noise reduction", noise_reduction.run)]
    for label, step in steps:
        print(label, flush=True)
        step(inp)
    if make_figure:
        print("[7/7] Figure 1", flush=True)
        pdf = figure.run(inp, figure_dir)
        if pdf:
            print(f"  wrote {pdf.relative_to(paths.REPO) if pdf.is_relative_to(paths.REPO) else pdf}")
    else:
        print("[7/7] Figure 1 skipped (--no-figure)")
    if check_tex is not None:
        print(f"checking the numbers printed in {check_tex.relative_to(paths.REPO) if check_tex.is_relative_to(paths.REPO) else check_tex}")
        status |= claims.check(inp, check_tex) != 0
    print(f"done in {time.time() - t0:.1f}s: {'ALL CHECKS PASSED' if status == 0 else 'CHECKS FAILED'}")
    return status


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m soctriage.analysis", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    ap.add_argument("--out", type=Path, default=paths.OUTPUTS, help="output directory (default: outputs/)")
    ap.add_argument("--no-figure", action="store_true", help="skip Figure 1 (matplotlib)")
    ap.add_argument("--paper-figure", action="store_true",
                    help="write Figure 1 into paper/source/figures/ (replaces the paper's figure PDF)")
    ap.add_argument("--no-check", action="store_true", help="skip the check of the numbers printed in the paper")
    ap.add_argument("--tex", type=Path, default=paths.PAPER_TEX, help="paper source to check")
    cp = sub.add_parser("compare", help="score retrained GUIDE predictions against the paper's")
    compare.add_arguments(cp)
    a = ap.parse_args(argv)
    if a.cmd == "compare":
        return compare.main(a)
    inp = Inputs(out=a.out)
    return run_all(inp, make_figure=not a.no_figure, check_tex=None if a.no_check else a.tex,
                   figure_dir=paths.PAPER_FIGURES if a.paper_figure else None)


if __name__ == "__main__":
    sys.exit(main())
