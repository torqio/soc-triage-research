# Released data

Everything the paper's analysis reads. `python3 -m soctriage.analysis` turns these files into `outputs/` and checks
the paper; `scripts/reproduce_guide.sh` validates the GUIDE files against the public dataset.

## `guide/`: public GUIDE (12 organizations, per prompt)

Prompt ids are `guide-<OrgId>-p<sha256(rendered prompt text)[:16]>`; incident ids are GUIDE's. Labels are prompt
majority labels. Every file covers the same 1,079 test prompts (456 malicious) and, except Opus, the same 1,079
validation prompts.

| File | Rows | Contents |
|---|---|---|
| `local_predictions/<method>/org_<id>.jsonl` | 2,158 per method | the six local models (`riskfit`, `ce`, `lightgbm`, `maxsim`, `knn`, `tiny_decision`): `alert_id` (prompt id), `split`, `expected_label`, `predicted_label`, `confidence` (max class probability), `class_probs` |
| `hosted_outputs/decisions_guide_per_prompt.csv` | 2,158 | Decisions API zero-shot (`zs_*`) and with one exemplar (`ex_*`): verdict, confidence, choice probabilities, predicate probability `p_mal_q2`; the exemplar's id, retrieval status and score |
| `hosted_outputs/jev_guide_per_prompt.csv` | 2,158 | Jev, same layout plus input token counts |
| `hosted_outputs/decisions_jev_5ex_guide_per_prompt.csv` | 2,158 | Decisions and Jev with 5 exemplars (`dec5_*`, `jev5_*`): exemplar ids, scores and labels, tie counts, sha256 of each request message |
| `hosted_outputs/decisions_jev_20ex_guide_per_prompt.csv` | 2,158 | the same with 20 exemplars (`dec20_*`, `jev20_*`) |
| `hosted_outputs/opus_guide_per_prompt.csv` | 2,158 | Claude Opus 5.5 on the test prompts, `condition` zs / ex: verdict, stated confidence, `p_malicious` |
| `hosted_outputs/cybersecqwen4b_zeroshot_guide_per_prompt.csv` | 2,158 | CyberSecQwen-4B zero-shot: verdict, confidence, label probabilities and summed log-probabilities, prompt tokens |
| `hosted_outputs/qwen3_4b_base_zeroshot_guide_per_prompt.csv` | 2,158 | its base model Qwen3-4B-Instruct, same layout |
| `prompt_membership.csv` | 71,576 | incident -> prompt -> split, incident and prompt labels (sha256 pre-registered in `configs/guide/selection.yaml`) |

An unresolved hosted call (empty verdict) counts as a non-malicious verdict with confidence 0.

## `production/`: private production alerts (aggregates only)

1,492 analyst-reviewed alerts from three anonymized tenants (A, B, C). The data owners permitted publication of
aggregate results only: every file is per tenant or pooled (`all`); `units/` holds tenant x fold x seed counts
for the two experiments whose tests use those units. No alert text, labels, per-alert scores or identifiers.
Counts are malicious alerts caught or missed and non-malicious alerts falsely escalated; cost = c x misses + FE.
`CE` is the benchmark run on a T4 GPU; `CE-A100 (lambda=0)` is the paired run on RiskFit's hardware.

| File | Contents | Paper |
|---|---|---|
| `data_summary.csv` | alerts per tenant and label, analyst corrections, agreement with the production LLM's verdict | Data |
| `gate80_test_quantile.csv` | 80% test-quantile gate (seed 42): misses, FE, malicious routed, alert-bootstrap intervals | Table 2 |
| `deployable_gate.csv` | deferral threshold from validation: misses, FE, automated share | Table 3 |
| `later_alerts_tenantA_gates.csv`, `later_alerts_tenantA_full_coverage.csv` | tenant A's 433 later alerts: both gates and full coverage | Table 3, later data |
| `later_alerts_local_models.csv` | tenant C's later export (not a forward test): full coverage, gates, coverage curve | later data |
| `default_verdicts.csv` | default verdicts at full coverage, kappa | full coverage, later data |
| `thresholds.csv` | validation-tuned p(malicious) thresholds at RiskFit's FPR and at 5% FPR | full automation |
| `one_to_one_vs_decisions_exemplar.csv` | each local model vs Decisions + exemplar: crossover c*, bootstrap interval | weighted cost |
| `seeds_riskfit_vs_ce_7seeds.csv`, `..._tests.csv`, `units/seeds_riskfit_vs_ce_7seeds_units.csv` | seven seeds of RiskFit and CE-A100: totals, paired differences, units | seeds, hinge text |
| `hinge_by_sampling_arms.csv`, `hinge_by_sampling_activity.csv`, `units/hinge_by_sampling_units.csv` | sampling x loss experiment over seeds 0-2: arms, hinge activity and training soft recall, units | Table 4 |
| `recall_target_sweep_monotonicity.csv` | realized recall for rho in {0.7, 0.8, 0.9, 0.95} | hinge text |
| `non_duplicate_subset.csv`, `near_duplicates.csv` | the 280-alert subset without a near-duplicate; duplicate shares | sensitivity |
| `evasion.csv` | misses under alert perturbations; condition `R0` removes the Response field | sensitivity, noise reduction |
| `accuracy_at_coverage.csv` | accuracy of the automated alerts at 100% and 80% coverage (pooled over folds) | confidence ranking |
| `decisions_repeatability.csv` | repeat calls of the Decisions API agree with the main run | reproducibility |
| `facts.csv` | scalar facts quoted in the text, with their location | text |

These numbers are outputs of `soctriage/evaluation.py` and the recipes in `configs/production/` on the private
folds; they cannot be recomputed here because the alerts are not released.
