"""Release rules: released data are public GUIDE identifiers or tenant-level / pooled aggregates, and the tree holds
no personal data, credentials or local paths (standard library only)."""

import csv
import hashlib
import json
import re
import subprocess
import unittest

from soctriage import paths

GUIDE_ID = re.compile(r"^guide-(\d+)-p[0-9a-f]{16}$")
ORGS = {r["org_id"] for r in csv.DictReader(paths.GUIDE_ORGS.open())}
ALLOWED_EMAILS = {"yaniv.zimmer@torq.io"}  # the corresponding author's contact (README)

_HOME = "/" + "Users/|/" + "home/|" + "C:" + r"\\Users"  # split so this file does not match itself
LEAKS = {
    "local path": re.compile(_HOME),
    "IPv4 address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "API key": re.compile(r"\b(?:sk-[A-Za-z0-9-]{16,}|AIza[0-9A-Za-z_-]{30,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{10,})"),
    "private key": re.compile("-----BEGIN [A-Z ]*PRIVATE" + " KEY-----"),
}
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Names of the production threat-intelligence enrichment providers (lower-case word tokens), stored only as
# sha256 so this file does not reveal them; they must not appear anywhere in the repository.
FORBIDDEN_TOKENS = {"ef2a33c946942c1a62de92bbd8e20bb3512b978032426b53ef754c308c8a6382",
                    "c7935003b01d7134049f24bfa71866b472667bc854da84de7c35362709151b33"}


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=paths.REPO, check=True,
                             capture_output=True, text=True).stdout.split("\n")
        return [paths.REPO / f for f in out if f]
    except (OSError, subprocess.CalledProcessError):
        skip = {"work", ".git", ".venv", "__pycache__"}
        return [p for p in paths.REPO.rglob("*") if p.is_file() and not skip & set(p.relative_to(paths.REPO).parts)]


class ReleasedGuideData(unittest.TestCase):
    def test_local_predictions_are_public_guide_prompts(self):
        dirs = sorted(p for p in paths.GUIDE_PREDICTIONS.iterdir() if p.is_dir())
        self.assertEqual([d.name for d in dirs], ["ce", "knn", "lightgbm", "maxsim", "riskfit", "tiny_decision"])
        for d in dirs:
            self.assertEqual({p.stem[4:] for p in d.glob("org_*.jsonl")}, ORGS)
            for p in d.glob("org_*.jsonl"):
                for line in p.open():
                    r = json.loads(line)
                    self.assertEqual(set(r), {"alert_id", "split", "expected_label", "predicted_label", "confidence", "class_probs"})
                    m = GUIDE_ID.match(r["alert_id"])
                    self.assertTrue(m and m.group(1) == p.stem[4:], r["alert_id"])
                    self.assertIn(r["split"], {"val", "test"})

    def test_hosted_outputs_are_public_guide_prompts(self):
        for p in paths.GUIDE_HOSTED.glob("*.csv"):
            for r in csv.DictReader(p.open(newline="")):
                for k, v in r.items():
                    if k == "id" or k.endswith("prompt_id"):
                        self.assertTrue(v == "" or GUIDE_ID.match(v), f"{p.name}:{k}={v}")
                self.assertIn(r["org"], ORGS)

    def test_membership_is_public_guide(self):
        with paths.GUIDE_MEMBERSHIP.open(newline="") as fh:
            for r in csv.DictReader(fh):
                self.assertIn(r["org_id"], ORGS)
                self.assertTrue(r["incident_id"].isdigit() and GUIDE_ID.match(r["prompt_id"]))


class ProductionAggregates(unittest.TestCase):
    def test_no_alert_level_columns(self):
        forbidden = re.compile(r"(alert_id|prompt_id|^id$|text|hostname|user|ip_|command|file_path|timestamp|detected_at|tenant_id)", re.I)
        for p in paths.PRODUCTION.rglob("*.csv"):
            header = next(csv.reader(p.open(newline="")))
            self.assertEqual([c for c in header if forbidden.search(c)], [], p.name)

    def test_tenants_are_anonymous(self):
        for p in paths.PRODUCTION.rglob("*.csv"):
            for r in csv.DictReader(p.open(newline="")):
                if "tenant" in r:
                    self.assertIn(r["tenant"], {"A", "B", "C", "all"}, p.name)
                if "scope" in r:
                    self.assertIn(r["scope"], {"A", "B", "C", "all"}, p.name)


class NoLeaks(unittest.TestCase):
    def test_no_personal_data_credentials_or_local_paths(self):
        hits = []
        for p in tracked_files():
            if p.suffix.lower() in {".pdf", ".png", ".jpg"}:
                continue
            s = p.read_text(errors="ignore")
            rel = p.relative_to(paths.REPO)
            hits += [(str(rel), name, m.group()) for name, rx in LEAKS.items() for m in rx.finditer(s)]
            hits += [(str(rel), "email", e) for e in EMAIL.findall(s) if e not in ALLOWED_EMAILS]
        self.assertEqual(hits, [])

    def test_no_enrichment_provider_names(self):
        hits = []
        for p in tracked_files():
            if p.suffix.lower() in {".pdf", ".png", ".jpg"}:
                continue
            s = p.read_text(errors="ignore")
            rel = str(p.relative_to(paths.REPO))
            if {_sha(t) for t in re.findall(r"[a-z0-9]+", s.lower())} & FORBIDDEN_TOKENS:
                hits.append((rel, "enrichment provider name"))
        self.assertEqual(hits, [])

    def test_no_binary_metadata_chunks_in_images(self):
        for p in tracked_files():
            if p.suffix.lower() == ".png":
                self.fail(f"{p}: PNG files may carry metadata chunks; the paper embeds the PDF figure")


if __name__ == "__main__":
    unittest.main()
