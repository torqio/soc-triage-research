"""The paper's analysis: every number, table and figure from the released results (standard library only;
Figure 1 also needs matplotlib). Run ``python -m soctriage.analysis``.

Modules, in pipeline order:
  data              loaders for the released GUIDE files and production aggregates
  gates, stats      gate rules, workflow metrics, exact Wilcoxon, Holm
  guide_gate        Table 2 (GUIDE), Figure 1 sweep, organization-level tests and bootstrap
  guide_validation  Table 3 (GUIDE), validation-FPR thresholds
  guide_incidents   GUIDE task construction and incident weighting
  production        Tables 2-4 (production), seeds, later alerts, confidence ranking
  noise_reduction   noise reduction (both datasets)
  figure            Figure 1
  claims            checks every listed number in paper/source/main.tex against the outputs
  compare           scores retrained GUIDE predictions against the paper's
"""
