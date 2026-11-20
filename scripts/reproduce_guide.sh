#!/usr/bin/env bash
# Reproduce and validate the paper's GUIDE results from the public GUIDE dataset.
#
#   scripts/reproduce_guide.sh                       download GUIDE, rebuild the benchmark, validate the released results
#   scripts/reproduce_guide.sh --train lightgbm      ... then retrain local models and compare them with the paper
#   scripts/reproduce_guide.sh --train all           ... all six local models (encoders need a GPU; see README)
#   scripts/reproduce_guide.sh --smoke               ... then a few-minute training run on one organization
#
# Options:
#   --train M1,M2|all   retrain these local models (riskfit, ce, lightgbm, maxsim, knn, tiny_decision)
#   --smoke             tiny training check: LightGBM and one-epoch RiskFit on 16 prompts of organization 77
#   --select            also re-run the pre-registered organization-selection walk (93 organizations, ~10 min)
#   --skip-download     use an existing work/guide/raw (GUIDE_Train.csv, GUIDE_Test.csv, archive.zip)
#   --python PY         Python interpreter (default: python3)
#
# Everything is written under work/ (git-ignored). Python packages: pip install -e ".[guide]" for steps 1-4,
# ".[train]" for training. No API key is needed; hosted models are not re-queried (see README).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3; TRAIN=""; SMOKE=0; SELECT=0; DOWNLOAD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --train) TRAIN="$2"; shift 2 ;;
    --smoke) SMOKE=1; shift ;;
    --select) SELECT=1; shift ;;
    --skip-download) DOWNLOAD=0; shift ;;
    --python) PY="$2"; shift 2 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "unknown option $1 (see --help)" >&2; exit 2 ;;
  esac
done
[ "$TRAIN" = "all" ] && TRAIN="riskfit,ce,lightgbm,maxsim,knn,tiny_decision"
W=work/guide
step() { printf '\n==== %s\n' "$*"; }

"$PY" - <<'EOF' || { echo 'missing packages: pip install -e ".[guide]"' >&2; exit 1; }
import pandas, sklearn, yaml  # noqa: F401
EOF

step "1/5 download and verify the public GUIDE dataset"
if [ "$DOWNLOAD" = 1 ]; then scripts/guide/download.sh "$W/raw"; else echo "skipped (--skip-download)"; fi

step "2/5 rebuild the 12-organization benchmark and check every split fingerprint"
"$PY" scripts/guide/build_splits.py --source-dir "$W/raw" --out "$W"
if [ "$SELECT" = 1 ]; then
  "$PY" scripts/guide/build_splits.py --source-dir "$W/raw" --out "$W/selection_walk" --select
fi

step "3/5 validate the released per-prompt results against the rebuilt benchmark"
"$PY" scripts/guide/validate_release.py --build-dir "$W"

step "4/5 rebuild the hosted-model requests (1, 5 and 20 exemplars) and compare with the released outputs"
for k in 1 5 20; do
  "$PY" scripts/guide/build_hosted_inputs.py --splits "$W/splits" --k "$k"
done

if [ -n "$TRAIN" ] || [ "$SMOKE" = 1 ]; then
  step "5/5 retrain local models and compare with the paper"
  PRED="$W/predictions"
  if [ "$SMOKE" = 1 ]; then
    PRED="$W/predictions_smoke"
    "$PY" scripts/guide/train.py --splits "$W/splits" --out "$PRED" --method lightgbm --orgs 77
    "$PY" scripts/guide/train.py --splits "$W/splits" --out "$PRED" --method riskfit --orgs 77 --epochs 1 --max-train 16
  fi
  for m in ${TRAIN//,/ }; do
    "$PY" scripts/guide/train.py --splits "$W/splits" --out "$PRED" --method "$m"
  done
  "$PY" -m soctriage.analysis compare --predictions "$PRED" --report "$W/compare_to_paper.csv"
else
  step "5/5 retraining skipped (use --train or --smoke)"
fi
printf '\nGUIDE reproduction finished: every check above passed.\n'
