"""The paper's analysis: gate rules, statistics, and an end-to-end rerun against outputs/ (standard library only)."""

import filecmp
import tempfile
import unittest
from pathlib import Path

from soctriage import paths
from soctriage.analysis import claims, gates, stats
from soctriage.analysis.__main__ import run_all
from soctriage.analysis.data import Inputs


def rec(i, y, pred, conf, pmal=0.0):
    return {"id": i, "y": y, "pred": pred, "conf": conf, "pmal": pmal}


class GateRules(unittest.TestCase):
    def test_n_keep_is_ceiling(self):
        self.assertEqual(gates.n_keep(0.8, 82), 66)   # ceil(65.6)
        self.assertEqual(gates.n_keep(0.8, 80), 64)   # exact, no float drift
        self.assertEqual(gates.n_keep(1.0, 7), 7)

    def test_ranking_breaks_ties_by_id_bytes(self):
        rs = [rec("b", "mal", "mal", 0.9), rec("a", "mal", "mal", 0.9), rec("c", "fp", "fp", 0.95)]
        self.assertEqual([r["id"] for r in gates.ranked(rs)], ["c", "a", "b"])

    def test_workflow_counts_deferred_as_correct(self):
        test = [rec("1", "mal", "fp", 0.9), rec("2", "fp", "mal", 0.8), rec("3", "mal", "mal", 0.7),
                rec("4", "ben", "ben", 0.6), rec("5", "mal", "fp", 0.1)]
        c = gates.counts(test, gates.gate_quantile(test, 0.8))  # automates 1-4, defers 5
        w = gates.workflow(c)
        self.assertEqual((w["misses"], w["false_esc"], w["automated"], w["TP"], w["TN"]), (1, 1, 4, 2, 1))
        self.assertAlmostEqual(w["workflow_recall"], 2 / 3)

    def test_tie_range_spans_tie_orders(self):
        test = [rec("1", "mal", "fp", 0.5), rec("2", "fp", "fp", 0.5), rec("3", "fp", "mal", 0.9)]
        tr = gates.tie_range(test, 0.6)  # keep ceil(1.8) = 2 of 3: the 0.9 one and one of two tied
        self.assertEqual((tr["miss_min"], tr["miss_max"], tr["fe_min"], tr["fe_max"]), (0, 1, 1, 1))

    def test_validation_thresholds(self):
        val = [rec(str(i), "fp", "fp", c) for i, c in enumerate([0.9, 0.8, 0.7, 0.6, 0.5])]
        self.assertEqual(gates.tau_validation(val, 0.8), 0.6)
        self.assertEqual(gates.np_threshold([0.9, 0.5, 0.1, 0.3], 0.25), 0.5)   # one of four may exceed
        self.assertEqual(gates.np_threshold([0.9, 0.5], 1.0), -1.0)


class Statistics(unittest.TestCase):
    def test_wilcoxon_exact(self):
        self.assertAlmostEqual(stats.wilcoxon_exact([1, 2, 3])[0], 0.25)
        self.assertAlmostEqual(stats.wilcoxon_exact([1, -2, 3, 4, 5])[0], 0.1875)
        self.assertEqual(stats.wilcoxon_exact([0, 0])[0], 1.0)

    def test_holm(self):
        self.assertEqual(stats.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


class Reproduction(unittest.TestCase):
    def test_rerun_matches_committed_outputs_and_paper(self):
        with tempfile.TemporaryDirectory() as d:
            status = run_all(Inputs(out=Path(d)), make_figure=False, check_tex=paths.PAPER_TEX)
            self.assertEqual(status, 0, "a released file failed its check or a printed number does not match")
            committed = sorted(p.relative_to(paths.OUTPUTS) for p in paths.OUTPUTS.rglob("*.csv"))
            rerun = sorted(p.relative_to(d) for p in Path(d).rglob("*.csv"))
            self.assertEqual(committed, rerun)
            for rel in committed:
                self.assertTrue(filecmp.cmp(paths.OUTPUTS / rel, Path(d) / rel, shallow=False), f"{rel} differs")

    def test_every_claim_is_printed_in_the_paper(self):
        tex = paths.PAPER_TEX.read_text()
        missing = [c.where for c in claims.CLAIMS if c.printed is not None and c.printed not in tex]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
