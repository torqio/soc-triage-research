# Local and Hosted Models for SOC Alert Triage Under Limited Human Review

Code, released results and a one-command reproduction for the paper by Yaniv Zimmer, Yuval Goldberg and Noam
Cohen (Torq). Contact: yaniv.zimmer@torq.io. The paper is
[`paper/local_hosted_soc_triage.pdf`](paper/local_hosted_soc_triage.pdf); its LaTeX source is in
[`paper/source/`](paper/source/).

The paper compares classifiers trained locally on each organization's analyst labels (RiskFit, CE, Tiny Decision,
MaxSim, kNN, LightGBM) with hosted classification APIs (OpenAI Decisions, TypeSafe Jev) and prompted LLMs (Gemini,
Claude Opus, CyberSecQwen-4B) when each method automates its 80% most confident alerts and defers the rest to
analysts. It uses 1,492 private production alerts from three tenants (released as aggregates only) and a
12-organization task built from the public Microsoft GUIDE dataset (released per prompt).

## Reproduce the paper (about one second, standard library only)

```bash
python3 -m soctriage.analysis
```

This recomputes every table and number in the paper from the released results in [`data/`](data/), writes them to
[`outputs/`](outputs/), draws Figure 1 (if matplotlib is installed) and checks **285 numbers printed in
[`paper/source/main.tex`](paper/source/main.tex)** against the recomputed values. It needs Python 3.10+ and no
packages, trains no model and calls no API. Expected ending:

```
  285 of 285 printed numbers verified; 1 known issue(s) listed in claims_check.csv
done in 1.0s: ALL CHECKS PASSED
```

The known issue is one value the released data do not support exactly (see [Known issues](#known-issues)).

Other entry points:

| Command | What it does |
|---|---|
| `make check` | recompute everything in a temporary directory and require it to be byte-identical to `outputs/` |
| `make test` | unit tests, the end-to-end rerun, and the release rules (no personal data, credentials or local paths) |
| `make figure` | draw Figure 1 into `outputs/figures/` (`pip install matplotlib`) |
| `python3 -m soctriage.analysis --help` | options (`--out`, `--no-figure`, `--paper-figure`, `--tex`) |

Where each table, figure and paragraph of the paper comes from: [`docs/paper_map.md`](docs/paper_map.md).

## Validate the GUIDE results from the public dataset (optional)

The released GUIDE predictions and hosted-model outputs can be checked against the public dataset, and the local
models retrained, with one script:

```bash
pip install -e ".[guide]"            # pandas, scikit-learn, pyyaml, pydantic
scripts/reproduce_guide.sh            # or: make guide
```

| Step | What is checked | Time |
|---|---|---|
| 1. Download | GUIDE (Kaggle, dataset version 2, about 540 MB; no Kaggle account needed) and its pre-registered sha256; the CSVs are read from the archive, so no 3.5 GB unpacking | network |
| 2. Rebuild the benchmark | the 12 organizations, distinct-prompt collapse and 70/15/15 splits; every split fingerprint, the membership and tie tables match the paper's | about 1 min |
| 3. Validate the released results | `data/guide/prompt_membership.csv` is byte-identical to the rebuilt one; every prompt id re-derives from its text; every released per-prompt file covers exactly the rebuilt prompts with the same labels; every exemplar is a training prompt of its organization | seconds |
| 4. Rebuild the hosted-model requests | instruction hashes, exemplar ids and the sha256 of every 5- and 20-exemplar message equal the released outputs | seconds |
| 5. Retrain (opt-in) | `--train lightgbm` (CPU, about 15 min), `--train riskfit,ce,...` or `--train all`, then `python3 -m soctriage.analysis compare` prints the paper's and the new Table 2 / Table 3 numbers side by side | see below |

Options: `--smoke` (a few-minute training run on one organization), `--select` (also re-run the pre-registered
organization-selection walk), `--skip-download`, `--python PY`. Everything is written to `work/` (git-ignored).
GUIDE is distributed by Microsoft on Kaggle under its own terms and is not redistributed here.

**Retraining.** `pip install -e ".[train]"` (Python 3.10-3.12; the pinned versions of the paper's runs). The encoders
download `cisco-ai/SecureBERT2.0-biencoder` (about 600 MB) and Tiny Decision `Qwen/Qwen3-0.6B-Base` from the
Hugging Face Hub. Paper's compute: RiskFit or CE about 3 A100-hours each for 12 organizations; MaxSim and Tiny
Decision 6.75 A100-hours together; kNN about 3 CPU node-hours (its GUIDE run used CPU embeddings); LightGBM about
15 minutes on 8 cores (macOS: `brew install libomp`). One training seed (42) was used. Retraining on other hardware
or library versions moves individual predictions, so expect small differences in counts; the comparison reports
how many test verdicts equal the paper's.

**Re-querying the hosted models.** Not needed for any check above. The clients are in
[`scripts/guide/hosted/`](scripts/guide/hosted/) and read keys only from the environment:

```bash
pip install -e ".[hosted]"
OPENAI_API_KEY=...    python3 scripts/guide/hosted/run_decisions.py --inputs work/guide/hosted_inputs.jsonl --out work/guide/requery/decisions_guide_per_prompt.csv
TYPESAFE_API_KEY=...  python3 scripts/guide/hosted/run_jev.py       --inputs work/guide/hosted_inputs.jsonl --out work/guide/requery/jev_guide_per_prompt.csv
ANTHROPIC_API_KEY=... python3 scripts/guide/hosted/run_opus.py      --inputs work/guide/hosted_inputs.jsonl --out work/guide/requery/opus_guide_per_prompt.csv
python3 scripts/guide/hosted/run_cybersecqwen.py --inputs work/guide/hosted_inputs.jsonl --model-dir work/models/CyberSecQwen-4B --check-tokens
```

Decisions (`gpt-6-luna`, queried 2026-10-29 to 11-05) and Jev (`jev-1.14.0`, 2026-11-01 to 11-05) have no dated
snapshots and Opus 5.5 (2026-11-03) was run once and is not deterministic, so a re-query can differ from the
released outputs. Approximate cost: Decisions and Jev about USD 1 for 0/1/5 exemplars and USD 1.33 for 20; Opus
about 3.8M input tokens. CyberSecQwen-4B and its base model run locally (about 8 GB each).

## Repository layout

```
paper/                  final PDF and LaTeX source (main.tex is what the analysis checks)
data/                   released results: the inputs of every number in the paper (see data/README.md)
  guide/                  public GUIDE: per-prompt outputs of 18 conditions, incident -> prompt membership
  production/             private production alerts: tenant-level or pooled aggregates only
outputs/                tables recomputed by `python3 -m soctriage.analysis` (committed reference copy)
soctriage/              Python package
  analysis/               the paper's analysis, standard library only (gates, statistics, tables, claims check)
  guide.py                GUIDE incident aggregation, distinct-prompt collapse, selection, splits, fingerprints
  serialization.py        normalized alert schema and the 21-field text renderer
  prompts.py, hosted.py   hosted-model instructions, label-blind exemplar retrieval, client plumbing
  models/                 local models: SecureBERT 2.0 + LoRA (RiskFit, CE, MaxSim, focal-Tversky) via vendored
                          FastFit, frozen-SecureBERT kNN, LightGBM, SetFit-LoRA, Qwen3-0.6B-LoRA (Tiny Decision)
  evaluation.py           production operating points, gates, bootstrap, paired tests (outputs are in data/production)
  evasion.py              alert perturbations and the Response-field removal check (R0)
configs/
  guide/                  pre-registered GUIDE selection rule, the 12 organizations, GUIDE model recipes
  production/             production model recipes (reference; the private data are not released)
scripts/
  reproduce_guide.sh      the GUIDE pipeline above
  guide/                  download.sh, build_splits.py, validate_release.py, build_hosted_inputs.py, train.py
  guide/hosted/           hosted and open-LLM clients
docs/                   paper map, reanalysis plan, release notes
tests/                  unit tests, end-to-end rerun, release rules
```

## Data and privacy

Production alerts are private; the data owners permitted publication of aggregate results only. This repository
contains no production alert text, labels, per-alert predictions, customer identifiers or trained adapters: every
production file is per tenant (`A`, `B`, `C`) or pooled (`all`), plus tenant x fold x seed counts for the seed and
hinge experiments. Production numbers can therefore be recomputed only from these aggregates, not from alerts. The
production recipes are in `configs/production/`; any split in the schema of `soctriage/serialization.py` can be
trained with `scripts/guide/train.py --config configs/production/<recipe>.yaml` (threat-intelligence enrichment in
the provider-neutral keys of `soctriage/serialization.py`). Only Google and OpenAI processed
production alerts; TypeSafe and Anthropic saw public GUIDE data only. See [`data/README.md`](data/README.md).

## Known issues

* The paper's later-alerts paragraph says the Decisions API's false-escalation rate "rose from 0.045 on the
  benchmark"; the released tenant A counts give 18 of 395 = 0.0456 (0.046). The claims check reports it as a known
  issue rather than a failure.
* Three statements in the paper are backed by a single released value rather than by recomputable counts:
  the 3,300 repeated Decisions calls, the Response value that identifies 7 of 17 malicious alerts, and Gemini's
  at most six confidence values per fold (`data/production/facts.csv`).
* Production results cannot be recomputed from alerts (see above); GUIDE local-model retraining is not bit-exact
  across hardware.

## Citation and license

See [`CITATION.cff`](CITATION.cff). Code under the Apache License 2.0 ([`LICENSE`](LICENSE));
`soctriage/models/fastfit/` is a modified copy of IBM FastFit (Apache-2.0). Changes from the 2026-11-19 release
package are listed in [`docs/release_notes.md`](docs/release_notes.md).
