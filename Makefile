PY ?= python3
METHODS ?= lightgbm

.PHONY: help reproduce check figure test guide guide-smoke guide-train

help:  ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | expand -t 16

reproduce:  ## every number, table and figure from the released results, checked against the paper
	$(PY) -m soctriage.analysis

check:  ## recompute every table in a temporary directory and require byte-identical outputs/
	@tmp=$$(mktemp -d) && $(PY) -m soctriage.analysis --no-figure --out $$tmp \
	  && diff -r -x figures outputs $$tmp && echo "outputs/ reproduced byte for byte"; \
	  status=$$?; rm -rf $$tmp; exit $$status

figure:  ## draw Figure 1 into outputs/figures/ (needs matplotlib)
	$(PY) -m soctriage.analysis --no-check

test:  ## unit and release tests
	$(PY) -m unittest discover -s tests -v

guide:  ## download GUIDE, rebuild the benchmark, validate the released GUIDE results
	scripts/reproduce_guide.sh --python $(PY)

guide-smoke:  ## guide + a few-minute training run on one organization
	scripts/reproduce_guide.sh --python $(PY) --smoke

guide-train:  ## guide + retrain METHODS (default lightgbm; "all" for six models) and compare with the paper
	scripts/reproduce_guide.sh --python $(PY) --train $(METHODS)
