# Analysis plan for the paper's revision (fixed before computing any revised test outcome)

> Repository note: this is the reanalysis plan as written on 2026-11-12. File paths were updated to this
> repository's layout and two internal code labels were replaced by descriptions; the rules are unchanged.

Written 2026-11-12 (UTC 19:15), before running any of the new analyses below. The authors of this plan had
already seen the submitted paper's test results (they are in the paper); what is fixed here is the rule for every
*new* number, so that no rule is chosen after looking at its revised test outcome. Any later deviation is listed
at the end of this file with its reason.

## Data used (no training, no new inference)
- GUIDE: released per-prompt outputs (`data/guide/local_predictions/*`, `data/guide/hosted_outputs/*`),
  12 organizations, 1,079 test prompts (456 malicious). Validation rows: every local model, Decisions and Jev
  (0/1/5/20 exemplars), CyberSecQwen-4B and Qwen3-4B base. Opus: test rows only -> excluded from every
  validation-dependent analysis (no substitution of test rows).
- GUIDE incident membership: `data/guide/prompt_membership.csv` (incident -> prompt -> split, labels).
- Production: aggregates only (`data/production/`). No per-alert data, so no new
  production thresholds or coverage sweeps.

## Definitions
- Positive class: malicious ("True Positive - Malicious" in local files, "malicious" in hosted files). An
  unresolved hosted call counts as a non-malicious verdict with confidence 0 (as in the release).
- Automated (auto-decided) alert: kept by the gate; deferred alert: routed to a human.
- Workflow confusion matrix over ALL evaluated alerts, assuming deferred alerts receive correct human verdicts:
  TP = auto true positives + deferred malicious; FN = auto malicious predicted non-malicious (unreviewed misses);
  FP = auto non-malicious predicted malicious (false escalations); TN = auto true negatives + deferred
  non-malicious. Workflow precision = TP/(TP+FP); workflow recall = TP/(TP+FN); automation rate = automated/all.
  Human-review count = deferred alerts + automated alerts escalated as malicious is NOT used; we report deferred
  count and false escalations separately. These are workflow metrics under an ideal-review assumption, not
  measured human performance. No F_beta in the main text.
- Weighted error cost (secondary only): c * misses + false escalations; c is a ratio, not money.

## Primary analysis: fixed review budget (retrospective matched coverage)
- Test-quantile gate, per organization: sort test rows by (-confidence, prompt id as UTF-8 bytes), automate
  ceil(round(coverage * n, 9)) rows; sum over organizations. Primary budget: 20% of alerts deferred
  (coverage 0.80). This is a retrospective matched-coverage comparison (the cutoff is set on test data), not a
  deployable threshold.
- Gate confidence: max class probability (local, open LLMs), the hosted model's own verdict confidence
  (Decisions, Jev), Opus's verbalized confidence (as in the release).
- Tie handling: point estimate uses the id-byte rule above; for every method and coverage we also report the
  min/max misses and false escalations over all tie orders at the cutoff.
- Reproduction gate: 80% must reproduce the paper (RiskFit 11/46, CE 15/35, LightGBM 31/39, MaxSim 38/17,
  kNN 21/28, Tiny Decision 12/30, Decisions + 1 ex. 8/420, Decisions + 20 ex. 12/90) and 100%: RiskFit 25/79,
  Decisions + 1 ex. 24/500. If not, stop and fix the code.

## Automation sweep
- Coverages 0.50, 0.55, ..., 1.00 for every GUIDE condition with the same gate and tie reporting.

## Validation-selected operating points (threshold transfer), GUIDE
Only methods with validation rows. All thresholds are computed from validation rows of the same organization.
1. Deferral threshold transfer: tau = confidence of the row at the 80% mark of the validation ranking
   (soctriage/evaluation.py tau_validation); automate test rows with conf >= tau. Report ACHIEVED test automation
   rate per method, with workflow metrics. Not workload-matched.
2. Full-automation p(malicious) thresholds (no deferral), Neyman-Pearson rule on validation non-malicious
   scores (soctriage/evaluation.py np_threshold): flag if score > t.
   - Primary target: fixed operational validation FPR of 5%.
   - Secondary target: RiskFit's VALIDATION false-positive rate at its default (argmax) verdict, per
     organization (replaces the released analysis, which used RiskFit's TEST FPR as the target).
   Score: p(malicious) for local/open models; predicate probability q2 for Decisions/Jev (as released).
   Reported: recall, FPR, misses, false escalations, achieved test FPR.
- Paired statistics for (2): organization-level recall differences, exact two-sided Wilcoxon signed-rank
  (zeros dropped) over the 12 organizations, Holm-corrected within each target over this fixed family:
  RiskFit vs each of {Decisions + 1 ex., Decisions + 20 ex., Jev + 20 ex.}, and CE vs the same three. Also the
  number of organizations favouring each side.

## Organization-level uncertainty (GUIDE)
- For the primary table: per-organization misses and false escalations; for the fixed pairs RiskFit vs
  Decisions + 20 ex., Tiny Decision vs Decisions + 20 ex., CE vs Decisions + 20 ex. and RiskFit vs
  Decisions + 1 ex.: number of organizations where the local model has fewer/more misses and fewer/more false
  escalations; exact Wilcoxon on per-organization differences (descriptive, not Holm-adjusted).
- Organization-cluster bootstrap (resample the 12 organizations with replacement, 2,000 replicates,
  random.Random(20261112)) of pooled workflow recall and false escalations at 80%: percentile 95% interval.
  Interpreted as variation across organizations like these, not as a probability of success in a new SOC.

## GUIDE task diagnostics
- From the membership file: incidents per split, prompts with mixed incident labels, majority ties, share of
  incidents whose label differs from their prompt's majority label (conflicting-label share), per split and for
  the test set.
- Incident-weighted sensitivity: give each test incident its prompt's automation decision and verdict; count
  malicious incidents (incident label) missed without review, and false escalations of non-malicious incidents,
  at 80% coverage and at full coverage, for the methods in the primary table.

## Production (aggregates only)
- Workflow metrics from existing counts: test-quantile 80% gate (seed 42, all methods), deployable gate
  (validation tau, achieved automation), default verdicts (100% automation), 7-seed RiskFit and CE-A100 at both
  gates (mean, sd across seeds), later tenant A alerts (achieved coverage). Production results are descriptive;
  three tenants.
- Production thresholds at "RiskFit's default FPR" used RiskFit's TEST FPR (the original release's analysis code) and cannot be recomputed
  without per-alert data: omitted. Production thresholds at a fixed 5% FPR (validation-tuned) are unaffected and
  may be reported.
- Recall hinge: report seeds of the natural-sampling rho .9 / lambda 2 arm from hinge_by_sampling_arms.csv and
  verify the per-seed sums from units/hinge_by_sampling_units.csv.

## Deviations
(none yet)

### Deviations and additions (recorded after the plan, 2026-11-12)
1. Wording: the line about "human-review count" above is garbled. What was computed: deferred alerts and false
   escalations are reported separately; no combined review count is used.
2. Added after seeing the incident-weighted result (exploratory, not pre-planned): `soctriage/analysis/guide_incidents.py` (incident concentration),
   which counts how concentrated test incidents are across prompts and how many of each method's missed incidents
   come from its single largest prompt. Reported in the paper as an explanation of the incident-weighted result.
3. The figure shows a fixed subset of conditions (RiskFit, CE, Tiny Decision, Decisions + 1 / + 20 ex.,
   Jev + 20 ex., Opus + 1 ex.) chosen to include the strongest hosted configurations; all 18 are in
   `outputs/guide/coverage_sweep.csv`.
4. Production thresholds at a fixed 5% validation FPR are taken from the released aggregate
   (`thresholds.csv`, "FPR 5%", validation-tuned per tenant-fold); they were not recomputed.
5. Production workflow precision/recall and automation rates are recomputed from integer counts; values that the
   CSVs store rounded are checked from counts in `soctriage/analysis/claims.py`.
