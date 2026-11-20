# Model recipes and the GUIDE selection rule

`guide/selection.yaml` is the pre-registered GUIDE organization selection and split rule; `guide/organizations.csv`
lists the 12 organizations with their counts and split fingerprints. Do not edit either: the fingerprints that
`scripts/guide/build_splits.py` checks depend on them (the hash salt `X4-GUIDE-org-` is part of the rule).

`guide/models/<method>.yaml` are the GUIDE recipes used by `scripts/guide/train.py --method <method>`
(riskfit, ce, lightgbm, maxsim, knn, tiny_decision; seed 42).

`production/` are the recipes of the production experiments. The production alerts are private, so these are
reference recipes: to train one on your own data, write each fold as `<splits>/org_<name>/{train,val,test}.jsonl`
records in the schema of `soctriage/serialization.py` (`NormalizedAlert`) plus `alert_id`, `label`
(`False Positive`, `True Positive - Benign`, `True Positive - Malicious`) and `label_source` (`gold` = analyst
corrected the LLM verdict, `silver` = analyst confirmed it), written with `soctriage.guide.render_jsonl`, next to a
`benchmark_split_manifest.json` of the form `{"splits": {"train": {"sha256": ...}, "val": {...}, "test": {...}}}`
(`soctriage.guide.split_metadata` computes each entry; `load_split` verifies them), then run

```bash
python3 scripts/guide/train.py --splits <splits> --orgs <name> --config configs/production/<recipe>.yaml --method <label> --seed <seed>
```

| Recipe | Paper |
|---|---|
| `riskfit.yaml` | RiskFit (rho 0.9, lambda 2, SupCon 0.5; analyst-corrected labels weighted 2:1), seed 42; seeds 42-48 in the seven-seed comparison; balanced hinge arm of Table 4 (seeds 0-2) |
| `riskfit_lambda0.yaml` | CE-A100 (lambda 0 on RiskFit's hardware): seven seeds; balanced CE arm of Table 4 (seeds 0-2) |
| `ce.yaml`, `maxsim.yaml`, `knn.yaml`, `lightgbm.yaml`, `qwen3_lora.yaml` | CE, MaxSim, kNN, LightGBM, Tiny Decision (Tables 2-3) |
| `riskfit_rho07.yaml`, `riskfit_rho08.yaml`, `riskfit_rho095.yaml` | recall-target sweep (rho 0.7-0.95, seeds 42-44) |
| `riskfit_lambda4.yaml`, `focal_tversky.yaml`, `setfit_lora.yaml` | production-only variants reported in the released aggregates |
| `hinge_by_sampling/*.yaml` | the remaining Table 4 arms (natural vs balanced sampling, seeds 0-2) |
