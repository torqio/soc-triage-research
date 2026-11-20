"""Figure 1: GUIDE misses and false escalations at automation rates 50-100%, from outputs/guide/coverage_sweep.csv.

Needs matplotlib (the only non-stdlib dependency of the analysis). The paper's LaTeX kit forbids CID fonts, so when
`rsvg-convert` (librsvg) is available the text is converted to outlines via SVG; otherwise the PDF embeds the
font as matplotlib writes it (fine for viewing, not for the paper). Writes
outputs/figures/guide_automation_sweep.{pdf,png} (git-ignored); `--paper-figure` writes the PDF into
paper/source/figures/ instead, replacing the paper's figure.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .data import Inputs, read_csv

# Times-compatible faces to match the paper text; DejaVu Serif is matplotlib's last resort.
TIMES_LIKE = ["Liberation Serif", "Nimbus Roman", "Times New Roman", "Times"]
# (condition, colour, line style, marker): local = solid + circle, API = dashed + square, Opus = dotted
SERIES = [
    ("RiskFit", "#2a78d6", "-", "o"),
    ("CE", "#1baf7a", "-", "o"),
    ("Tiny Decision", "#6250d6", "-", "o"),
    ("Decisions + 1 ex.", "#eb6834", "--", "s"),
    ("Decisions + 20 ex.", "#e34948", "--", "s"),
    ("Jev + 20 ex.", "#eda100", "--", "s"),
    ("Opus + 1 ex.", "#e87ba4", ":", "^"),
]


def run(inp: Inputs, fig_dir: Path | None = None) -> Path | None:
    fig_dir = fig_dir or inp.out / "figures"
    try:
        import matplotlib
    except ImportError:
        print("  figure skipped: matplotlib is not installed (pip install matplotlib)")
        return None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = read_csv(inp.out / "guide" / "coverage_sweep.csv")
    plt.rcParams.update({"font.size": 9, "font.family": "serif", "font.serif": TIMES_LIKE,
                         "mathtext.fontset": "stix", "axes.spines.top": False, "axes.spines.right": False,
                         "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                         "legend.frameon": False, "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.75), constrained_layout=True)
    for name, color, ls, mk in SERIES:
        rr = sorted((r for r in rows if r["method"] == name), key=lambda r: float(r["automation_rate"]))
        if not rr:
            continue
        x = [100 * float(r["automation_rate"]) for r in rr]
        for ax, key, lo, hi in ((axes[0], "misses", "misses_tie_min", "misses_tie_max"),
                                (axes[1], "false_esc", "fe_tie_min", "fe_tie_max")):
            ax.plot(x, [int(r[key]) for r in rr], ls=ls, color=color, lw=1.4, marker=mk, ms=3.2, label=name)
            if name.startswith("Opus"):  # Opus's stated confidence ties heavily: shade the range over tie orders
                ax.fill_between(x, [int(r[lo]) for r in rr], [int(r[hi]) for r in rr], color=color, alpha=0.18, lw=0)
    axes[0].set_ylabel("Unreviewed misses (of 456)")
    axes[1].set_ylabel("False escalations (of 623)")
    axes[1].set_yscale("log")
    axes[1].set_yticks([5, 10, 20, 50, 100, 200, 500])
    axes[1].set_yticklabels(["5", "10", "20", "50", "100", "200", "500"])
    axes[1].minorticks_off()
    for ax, title in zip(axes, ("(a) malicious prompts automated as non-malicious", "(b) non-malicious prompts escalated")):
        ax.set_xlabel("Automation rate (%)")
        ax.set_xlim(49, 101)
        ax.axvline(80.4, color="#8a8984", lw=0.6, ls="-", zorder=0)  # the 80% budget (868 of 1,079 prompts)
        ax.grid(axis="y", color="#e4e3df", lw=0.5)
        ax.set_title(title, fontsize=9, loc="left")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=4, fontsize=9, handlelength=2.4, columnspacing=1.2)

    fig_dir.mkdir(parents=True, exist_ok=True)
    pdf = fig_dir / "guide_automation_sweep.pdf"
    if shutil.which("rsvg-convert"):
        svg = fig_dir / "guide_automation_sweep.svg"
        plt.rcParams["svg.fonttype"] = "path"
        fig.savefig(svg)
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(pdf), str(svg)], check=True)
        svg.unlink()
    else:
        print("  rsvg-convert not found (brew install librsvg): PDF written with embedded fonts, not outlines")
        fig.savefig(pdf)
    fig.savefig(fig_dir / "guide_automation_sweep.png", dpi=200)
    plt.close(fig)
    return pdf
