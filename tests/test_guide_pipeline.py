"""The GUIDE benchmark builder on a small synthetic GUIDE extract (needs pandas and scikit-learn; skipped otherwise),
and the accumulation-window recall hinge (needs torch; skipped otherwise). The real-data checks are in
scripts/reproduce_guide.sh."""

import csv
import hashlib
import random
import tempfile
import types
import unittest
from pathlib import Path

try:
    import pandas  # noqa: F401
    import sklearn  # noqa: F401
    HAVE_GUIDE_DEPS = True
except ImportError:
    HAVE_GUIDE_DEPS = False

try:
    import torch
except ImportError:
    torch = None

COLUMNS = ["Id", "OrgId", "IncidentId", "AlertId", "Timestamp", "Category", "MitreTechniques", "EntityType",
           "EvidenceRole", "IncidentGrade"]


def synthetic_guide(d: Path, org="999", incidents=900, seed=0):
    """Evidence rows in the GUIDE column layout: several rows per incident, three grades, some repeated texts."""
    rng = random.Random(seed)
    cats = ["InitialAccess", "Execution", "Persistence", "Exfiltration", "Discovery", "Impact", "CommandAndControl"]
    ents = ["Ip", "User", "Machine", "File", "Process", "Url", "MailMessage"]
    roles = ["Impacted", "Related"]
    grades = ["TruePositive"] * 3 + ["BenignPositive"] * 4 + ["FalsePositive"] * 3
    rows = []
    for inc in range(incidents):
        grade = rng.choice(grades)
        for _ in range(rng.randint(1, 4)):
            rows.append({"Id": len(rows), "OrgId": org, "IncidentId": 1000 + inc, "AlertId": len(rows),
                         "Timestamp": f"2024-06-{rng.randint(1, 28):02d}T10:00:00.000Z", "Category": rng.choice(cats),
                         "MitreTechniques": rng.choice(["", f"T{rng.randint(1000, 1600)}"]),
                         "EntityType": rng.choice(ents), "EvidenceRole": rng.choice(roles), "IncidentGrade": grade})
    rows.append({**rows[0], "IncidentGrade": "FalsePositive" if rows[0]["IncidentGrade"] != "FalsePositive" else "TruePositive"})
    half = len(rows) // 2
    for name, part in (("GUIDE_Train.csv", rows[:half]), ("GUIDE_Test.csv", rows[half:])):
        with (d / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(part)


@unittest.skipUnless(HAVE_GUIDE_DEPS, "pandas and scikit-learn are not installed (pip install -e '.[guide]')")
class BenchmarkBuilder(unittest.TestCase):
    def test_build_split_and_reload(self):
        from soctriage import guide as G
        from soctriage.serialization import render_alert

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            synthetic_guide(tmp)
            grouped = G.aggregate_incidents(tmp, {"999"})
            ids = {r["alert_id"] for r in grouped["999"]}
            self.assertNotIn("guide-999-1000", ids, "the incident with two grades must be dropped")
            built = G.build_org("999", grouped["999"])
            self.assertNotIn("skip", built, built.get("skip"))
            G.write_org(tmp / "out", "999", built, archive_sha256=None)
            splits = G.load_split(tmp / "out" / "splits", "999")  # verifies hashes against the manifest
            n = {k: len(v) for k, v in splits.items()}
            total = sum(n.values())
            self.assertAlmostEqual(n["test"] / total, 0.15, delta=0.01)
            self.assertAlmostEqual(n["val"] / total, 0.15, delta=0.01)
            for recs in splits.values():
                for r in recs:  # prompt id = hash of the rendered text, as validate_release.py checks on GUIDE
                    want = f"guide-999-p{hashlib.sha256(render_alert(r).encode()).hexdigest()[:16]}"
                    self.assertEqual(r["alert_id"], want)
            self.assertEqual(len(built["membership"]), len(grouped["999"]))
            again = G.build_org("999", G.aggregate_incidents(tmp, {"999"})["999"])
            self.assertEqual(again["row"]["split_fingerprint"], built["row"]["split_fingerprint"], "builder is deterministic")


    def test_reading_from_the_archive_equals_unpacked_files(self):
        import zipfile

        from soctriage import guide as G

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "csv").mkdir()
            (tmp / "zip").mkdir()
            synthetic_guide(tmp / "csv", incidents=200)
            with zipfile.ZipFile(tmp / "zip" / "archive.zip", "w", zipfile.ZIP_DEFLATED) as zf:
                for name in G.FILES:
                    zf.write(tmp / "csv" / name, name)
            self.assertEqual(G.aggregate_incidents(tmp / "csv", {"999"}, chunksize=97),
                             G.aggregate_incidents(tmp / "zip", {"999"}, chunksize=97))
            self.assertTrue(G.org_label_counts(tmp / "csv").equals(G.org_label_counts(tmp / "zip")))


@unittest.skipUnless(torch is not None, "torch is not installed (pip install -e '.[train]')")
class WindowHinge(unittest.TestCase):
    def test_accumulation_window_gradient_equals_one_graph_hinge(self):
        from soctriage.models.fastfit.modeling import FastFitTrainable

        class Stub(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.lin = torch.nn.Linear(5, 3)
                self.config = types.SimpleNamespace(recall_constraint_rho=0.9, recall_hinge_window="accum",
                                                    false_positive_penalty_beta=0.0, sim_factor=0.5,
                                                    recall_constraint_lambda=2.0)

        for name in ("hinge_window_begin", "_hinge_stats", "_hinge_unit", "_window_hinge"):
            setattr(Stub, name, getattr(FastFitTrainable, name))
        torch.manual_seed(0)
        X = [torch.randn(4, 5) for _ in range(3)]
        Y = [torch.tensor([2, 0, 1, 0]), torch.tensor([0, 0, 1, 0]), torch.tensor([2, 2, 0, 1])]
        ref = Stub()
        p = torch.cat([torch.softmax(ref.lin(x), 1)[:, 2] for x in X])
        (2.0 * torch.relu(0.9 - p[torch.cat(Y) == 2].mean())).backward()
        m = Stub()
        m.load_state_dict(ref.state_dict())
        m.hinge_window_begin(3)
        for x, y in zip(X, Y):
            pr = torch.softmax(m.lin(x), 1)[:, 2]
            (m._window_hinge(pr, y == 2, torch.tensor(2.0)) / 3 + 0 * pr.sum()).backward()
        for a, b in zip(ref.parameters(), m.parameters()):
            self.assertTrue(torch.allclose(a.grad, b.grad, atol=1e-6))


if __name__ == "__main__":
    unittest.main()
