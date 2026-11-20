# Release notes

## 1.0.0: first release

Built from the release package of 2026-11-19 (`riskfit-release`). That package held the code of the original
analysis, its outputs for an earlier version of the paper, and a reanalysis folder that reproduces the
final paper. This repository keeps what the final paper needs and makes it reproducible with one command.

### Reproduction
* The final paper's analysis (the package's reanalysis scripts, steps 01-10) is the package `soctriage.analysis`,
  run with `python3 -m soctriage.analysis`. Its tables are byte-identical to the package's
  reanalysis outputs except for two deliberate changes: `outputs/guide/incident_weighted.csv` adds the
  share of incidents automated (quoted in the paper, previously not in any output), and
  `outputs/production/hinge_by_sampling_seeds.csv` drops a row that summarized an earlier abstract.
* The paper check covers 285 printed numbers (the package's checker: 238). The added checks cover the text ranges
  and counts of the GUIDE, production, sweep, later-data, sensitivity and limitations paragraphs. One printed
  value does not match the released data and is reported as a known issue (README).
* New: `scripts/reproduce_guide.sh` downloads GUIDE without a Kaggle account (and reads it from the archive, so
  it needs 540 MB of disk instead of 4 GB), rebuilds the benchmark,
  and validates the released per-prompt results against it (`scripts/guide/validate_release.py`), then optionally
  retrains and compares (`python3 -m soctriage.analysis compare`).
* Output file names describe their content (`02_guide_sweep.csv` -> `outputs/guide/coverage_sweep.csv`, ...).
* Package `riskfit` renamed `soctriage`; scripts moved to `scripts/guide/` and `scripts/guide/hosted/`;
  configs to `configs/guide/` and `configs/production/`; outputs of the optional pipeline go to `work/`.
* Tests rewritten for this layout (`make test`): gate rules, statistics, the end-to-end rerun against
  `outputs/`, released-data rules, a synthetic GUIDE build, and the window-hinge gradient (with torch).

### Removed (not used by the final paper)
* The original GUIDE analysis `scripts/analyze_guide.py`, its snapshot `aggregates/guide/` and
  `paper_numbers.txt`, and `scripts/make_figures.py`: they produce the earlier version's Tables 1-6 and
  Figures 1-2. The final paper's GUIDE numbers come from `soctriage.analysis`.
* Production aggregates that back no number in the final paper: weak supervision
  (`weak_supervision.csv`, `weak_vs_revealed_*`), `ranking_auc.csv`, `gate80_crossovers_bootstrap.csv`,
  `gate80_min_cost_probability.csv`, `beta025_seed_change.csv` (and its recipe), `recall_target_sweep_tests.csv`,
  `units/recall_target_sweep_units.csv`, `hinge_by_sampling_contrasts.csv`, `field_lookup_predictiveness.csv`;
  four rows of `facts.csv` (weak supervision, P3 indicator).
* The earlier README's paper-to-repository map and `SCRUB_REPORT.md`, which described the earlier version;
  replaced by `docs/paper_map.md` and this file.

### Privacy fixes (from an audit of the package)
* `production_risk_coverage.csv` (684 rows: per-tenant x method x coverage values with per-fold columns and folds
  with at most one malicious alert) is replaced by `data/production/accuracy_at_coverage.csv`: the eight pooled
  per-tenant values the paper quotes.
* Removed the figure PNG, which carried an embedded content-provenance manifest; the paper embeds the PDF.
* Removed an internal-tooling comment from `main.tex` and provenance comments from `refs.bib` (no entry changed).
* `docs/analysis_plan.md`: internal results paths and code labels replaced by repository paths (rules unchanged).
* Threat-intelligence enrichment is provider neutral: the provider-specific payload mappers of the production
  export were removed, enrichment results are supplied in the keys of `soctriage.serialization.ENRICHMENT_KEYS`,
  and two rendered keys were renamed to `ti_verdict` and `ti_threat_score` (GUIDE renders no enrichment, so every
  GUIDE prompt and split is unchanged; verified against the dataset). `tests/test_release.py` guards the provider
  names by hash.
* Git history starts at this release (no earlier commits are carried over).
* No production alert text, labels, per-alert scores, customer identifiers, credentials or local paths;
  `tests/test_release.py` enforces this on every file.
