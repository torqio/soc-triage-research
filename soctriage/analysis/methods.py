"""The 18 GUIDE conditions of the paper and where their per-prompt outputs live."""

from __future__ import annotations

MAL_LOCAL = "True Positive - Malicious"

# label normalization: mal | ben | fp | unresolved
HOSTED_LABEL = {"malicious": "mal", "benign": "ben", "false_positive": "fp", "": "unresolved", None: "unresolved"}
LOCAL_LABEL = {"True Positive - Malicious": "mal", "True Positive - Benign": "ben", "False Positive": "fp"}

# Local models: display name -> directory under data/guide/local_predictions/
LOCAL = {"RiskFit": "riskfit", "CE": "ce", "LightGBM": "lightgbm", "MaxSim": "maxsim", "kNN": "knn",
         "Tiny Decision": "tiny_decision"}

# Hosted classification APIs: (display name, file in data/guide/hosted_outputs/, column prefix)
DECISION_FILES = [
    ("Decisions 0-shot", "decisions_guide_per_prompt.csv", "zs"),
    ("Decisions + 1 ex.", "decisions_guide_per_prompt.csv", "ex"),
    ("Decisions + 5 ex.", "decisions_jev_5ex_guide_per_prompt.csv", "dec5"),
    ("Decisions + 20 ex.", "decisions_jev_20ex_guide_per_prompt.csv", "dec20"),
    ("Jev 0-shot", "jev_guide_per_prompt.csv", "zs"),
    ("Jev + 1 ex.", "jev_guide_per_prompt.csv", "ex"),
    ("Jev + 5 ex.", "decisions_jev_5ex_guide_per_prompt.csv", "jev5"),
    ("Jev + 20 ex.", "decisions_jev_20ex_guide_per_prompt.csv", "jev20"),
]
# Claude Opus (test prompts only): (display name, value of the `condition` column)
OPUS_FILE = "opus_guide_per_prompt.csv"
OPUS = [("Opus 0-shot", "zs"), ("Opus + 1 ex.", "ex")]
# Open LLMs scored locally: (display name, file)
OPEN = [("CyberSecQwen-4B", "cybersecqwen4b_zeroshot_guide_per_prompt.csv"),
        ("Qwen3-4B base", "qwen3_4b_base_zeroshot_guide_per_prompt.csv")]

METHODS = list(LOCAL) + [d[0] for d in DECISION_FILES] + [o[0] for o in OPUS] + [o[0] for o in OPEN]
GROUP = {**{m: "local" for m in LOCAL}, **{d[0]: "hosted classification API" for d in DECISION_FILES},
         **{o[0]: "prompted LLM (hosted)" for o in OPUS}, **{o[0]: "prompted LLM (open, local)" for o in OPEN}}
