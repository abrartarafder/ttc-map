"""
Export report-ready degree centrality outputs from the TTC node metrics table.

This script reads the existing `outputs/ttc_node_metrics.csv`, adds the
degree_centrality column if needed, and writes a few artifacts that are easier
to use in a report or Overleaf:

  - outputs/ttc_node_metrics.csv
  - outputs/ttc_degree_centrality_top15.csv
  - outputs/ttc_degree_centrality_top15.tex
  - outputs/ttc_degree_centrality_top15.png

Run from the project root:
    python algos/export_degree_centrality_outputs.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"
METRICS_PATH = OUTPUT_DIR / "ttc_node_metrics.csv"
TOP_N = 15


def main() -> None:
    if not METRICS_PATH.exists():
        raise FileNotFoundError(f"Missing metrics file: {METRICS_PATH}")

    df = pd.read_csv(METRICS_PATH)
    if "degree" not in df.columns:
        raise ValueError("ttc_node_metrics.csv must contain a degree column")

    node_count = len(df)
    if node_count < 2:
        raise ValueError("Need at least two nodes to compute degree centrality")

    # Degree centrality for a directed graph uses total degree / (n - 1).
    df = df.copy()
    df["degree_centrality"] = df["degree"] / (node_count - 1)

    # Keep the main metrics file up to date with the new column.
    df.to_csv(METRICS_PATH, index=False)

    top = (
        df.sort_values(
            ["degree_centrality", "degree", "pagerank", "betweenness"],
            ascending=[False, False, False, False],
        )
        .head(TOP_N)
        .loc[:, ["stop_id", "name", "degree", "degree_centrality", "pagerank", "betweenness"]]
        .reset_index(drop=True)
    )

    top_csv = OUTPUT_DIR / "ttc_degree_centrality_top15.csv"
    top_tex = OUTPUT_DIR / "ttc_degree_centrality_top15.tex"
    top_png = OUTPUT_DIR / "ttc_degree_centrality_top15.png"

    top.to_csv(top_csv, index=False)
    top.to_latex(top_tex, index=False, float_format=lambda x: f"{x:.6f}", escape=True)

    plot_df = top.sort_values("degree_centrality", ascending=True)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(
        plot_df["name"],
        plot_df["degree_centrality"] * 100,
        color="#2563eb",
        edgecolor="white",
    )
    ax.set_xlabel("Degree centrality (%)")
    ax.set_ylabel("Stop")
    ax.set_title("TTC Stop Network - Top 15 by Degree Centrality")
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=2))
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    plt.tight_layout()
    fig.savefig(top_png, dpi=150)
    plt.close(fig)

    summary = pd.DataFrame(
        {
            "metric": [
                "node_count",
                "degree_centrality_min",
                "degree_centrality_mean",
                "degree_centrality_median",
                "degree_centrality_max",
                "top_stop_id",
                "top_stop_name",
                "top_stop_degree",
                "top_stop_degree_centrality",
            ],
            "value": [
                node_count,
                df["degree_centrality"].min(),
                df["degree_centrality"].mean(),
                df["degree_centrality"].median(),
                df["degree_centrality"].max(),
                top.loc[0, "stop_id"],
                top.loc[0, "name"],
                top.loc[0, "degree"],
                top.loc[0, "degree_centrality"],
            ],
        }
    )
    summary.to_csv(OUTPUT_DIR / "ttc_degree_centrality_summary.csv", index=False)

    print(f"Wrote {METRICS_PATH}")
    print(f"Wrote {top_csv}")
    print(f"Wrote {top_tex}")
    print(f"Wrote {top_png}")
    print(f"Wrote {OUTPUT_DIR / 'ttc_degree_centrality_summary.csv'}")


if __name__ == "__main__":
    main()
