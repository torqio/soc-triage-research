# Paper-to-repository map

Every table, figure and quantitative paragraph of the final paper
([`paper/source/main.tex`](../paper/source/main.tex)), the output that reproduces it and the code that computes it.
`outputs/` paths are written by `python3 -m soctriage.analysis`; `data/` paths are released inputs.
Each printed number is also listed, with its source row, in [`outputs/claims_check.csv`](../outputs/claims_check.csv)
(285 checks); `soctriage/analysis/claims.py` defines them.

## Tables and figure

| Paper element | Output (and inputs) | Code |
|---|---|---|
| Table 1 (compared systems) | descriptive; recipes in `configs/guide/models/`, `configs/production/` | `soctriage/models/`, `soctriage/prompts.py`, `scripts/guide/hosted/` |
| Table 2, GUIDE block (80% gate, 1,079 prompts) | `outputs/guide/gate80_workflow.csv`; tie ranges in `outputs/guide/coverage_sweep.csv` (from `data/guide/`) | `analysis/guide_gate.py` |
| Table 2, production block | `outputs/production/gate80_workflow.csv` (from `data/production/gate80_test_quantile.csv`) | `analysis/production.py` |
| Figure 1 (automation sweep 50-100%) | `outputs/guide/coverage_sweep.csv`; drawn to `outputs/figures/` (the paper's PDF figure is in `paper/source/figures/`) | `analysis/guide_gate.py`, `analysis/figure.py` |
| Table 3, GUIDE block (validation deferral threshold) | `outputs/guide/validation_deferral_gate.csv` | `analysis/guide_validation.py` |
| Table 3, production block | `outputs/production/validation_deferral_gate.csv` (from `deployable_gate.csv`) | `analysis/production.py` |
| Table 3, tenant A later alerts | `outputs/production/later_tenant_a_workflow.csv` (from `later_alerts_tenantA_gates.csv`) | `analysis/production.py` |
| Table 4 (recall hinge by sampling) | `outputs/production/hinge_by_sampling_seeds.csv` (recomputed from `units/hinge_by_sampling_units.csv`) | `analysis/production.py` |

## Text

| Paper place | Numbers | Source |
|---|---|---|
| Abstract | 12 misses each, 30 vs 90 false escalations | Table 2, GUIDE block |
| Task and Evaluation Protocol, Uncertainty | 2,000 organization-cluster bootstrap replicates | `outputs/guide/gate80_cluster_bootstrap.csv` |
| Data, production alerts | 412 / 707 / 373 alerts, 17 / 39 / 17 malicious, 528 corrections (six to malicious), 943 of 964; 33.5% duplicates; Response value 7 of 17; 433 later alerts | `data/production/data_summary.csv`, `near_duplicates.csv`, `facts.csv`, `later_alerts_tenantA_full_coverage.csv` |
| Data, GUIDE-derived task | 71,576 incidents, 7,160 prompts, 414 mixed (5.8%), 3.2% conflicting; 1,079 test prompts (456 / 623) from 9,722 incidents; 11 prompts hold 52% | `outputs/guide/task_label_conflicts.csv`, `incident_concentration.csv` |
| Comparison at a fixed review budget, GUIDE | 0 to 16 misses (Jev + 1 ex.: 27), 241 to 502 FE, precision .48-.65; organization counts and exact Wilcoxon p (0.97, 0.005, 0.066); bootstrap intervals | `outputs/guide/gate80_workflow.csv`, `gate80_org_paired_tests.csv`, `gate80_cluster_bootstrap.csv` |
| Comparison at a fixed review budget, production | 7 to 16 misses, 2 to 28 FE; Gemini six confidence values; seven seeds 9.3 +- 2.0 (5-11), 16.0 +- 6.2 (9-28), CE 9.3 +- 2.6, 11.3 +- 3.4 | `outputs/production/gate80_workflow.csv`, `seeds_workflow.csv`; `data/production/facts.csv` |
| Noise reduction | 69-80% vs 63% (GUIDE), 78-82% vs 69% (production); recall .967-.976 vs .974 | `outputs/noise_reduction.csv` |
| Confidence ranking | RiskFit 91.0 -> 96.1%, 75.1 -> 79.7%, 95.4 -> 99.7%; Gemini B 51.3% / 50.5% | `outputs/production/confidence_ranking.csv` (from `accuracy_at_coverage.csv`) |
| Weighted error cost | crossovers about 14 / 16 / 21 (MaxSim 11-71); GUIDE dominance; CE up to c = 18 | `data/production/one_to_one_vs_decisions_exemplar.csv`; `outputs/guide/gate80_workflow.csv` |
| Performance across automation rates | at least 120 / 48-126 / 5-79 FE; at 90%: 12 and 14 vs 16-22; full coverage 25/79, 27/70, 33/50, 22/126, 24/500; production 2 of 73 / 213, 17/64, 22/36 | `outputs/guide/coverage_sweep.csv`, `outputs/production/default_verdicts_workflow.csv` |
| Validation-selected thresholds and later data | automation 78-84% (GUIDE), 74.5-84.5% (production), organizations 60-98%; later 15 / 20 / 39 / 72 / 93%; at 80%: 2 of 11 with 1, 2/0, 2/28, 1/56; FE rate 0.045 -> 0.18 (see known issues); 66% vs 38%; tenant C 295 of 1,034 | `outputs/guide/validation_deferral_gate.csv`, `outputs/production/validation_deferral_gate.csv`, `later_tenant_a_workflow.csv`; `data/production/later_alerts_*.csv`, `facts.csv`, `default_verdicts.csv` |
| Full automation (one sentence) | Holm p >= 0.39; 5% validation FPR lowers recall for every method | `outputs/guide/validation_fpr_threshold_tests.csv`, `validation_fpr_thresholds.csv` |
| Incident weighting | 1 to 1,317 incidents per prompt; 83.6 / 72.7 / 68.0% of incidents automated; 26 and 30 of 4,259; 535 (508 from one prompt); 188 of 5,463, 581, 363 | `outputs/guide/incident_weighted.csv`, `incident_concentration.csv` |
| Duplication and leakage | 280 alerts (37 malicious): 4/7, 3/1, 5/1, 0/66; Response removed: 9->8, 9->10, 16->18, 0->2 | `data/production/non_duplicate_subset.csv`, `evasion.csv` (condition R0) |
| Secondary ablation | Eq. 1 with rho 0.9, lambda 2, gamma 0.5; seeds 46, 50, 42; 45.3 and 47.0; about 28.7 more FE; soft recall 0.36 -> 0.99; recall 0.72-0.74; +0.6 caught, +9 FE | `outputs/production/hinge_by_sampling_seeds.csv`; `data/production/hinge_by_sampling_activity.csv`, `recall_target_sweep_monotonicity.csv`, `seeds_riskfit_vs_ce_7seeds_tests.csv`; loss in `soctriage/models/fastfit/modeling.py` (`lagrangian_recall_loss`, `_window_hinge`), sampler in `train.py` (`MaliciousBalancedBatchSampler`), recipes `configs/production/riskfit*.yaml`, `hinge_by_sampling/` |
| Limitations | four organizations with 3, 4, 13, 17 non-malicious validation prompts hold 287 of 456 malicious test prompts | `outputs/guide/task_label_conflicts.csv` |
| Reproducibility | 3,300 repeated Decisions calls | `data/production/facts.csv`, `decisions_repeatability.csv` |

## Methods

| Paper statement | Where |
|---|---|
| Gate: rank by confidence, automate ceil(0.8 n) per organization or tenant-fold, ties by alert id | `soctriage/analysis/gates.py` (`gate_quantile`, `ranked`); production: `soctriage/evaluation.py` |
| Deferral threshold at 80% validation coverage; Neyman-Pearson thresholds on p(malicious) | `gates.tau_validation`, `gates.np_threshold` |
| Workflow precision / recall, noise reduction under the ideal-review assumption | `gates.workflow`, `analysis/noise_reduction.py` |
| Exact Wilcoxon, Holm, organization-cluster bootstrap | `analysis/stats.py`, `analysis/guide_gate.py` |
| Pre-registered GUIDE selection, distinct-prompt unit, 70/15/15 split | `configs/guide/selection.yaml`, `soctriage/guide.py`, `scripts/guide/build_splits.py` |
| Label-blind exemplar retrieval; hosted-model instructions | `soctriage/prompts.py`, `scripts/guide/build_hosted_inputs.py` |
| Reanalysis plan fixed before the revised outcomes | [`docs/analysis_plan.md`](analysis_plan.md) |
