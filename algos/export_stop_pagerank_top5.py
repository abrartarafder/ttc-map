"""
Export the top 5 TTC stops by PageRank from the stop-level metrics table.

This is the stop-level companion to the historical hub ranking:
  - stop-level PageRank is based on individual GTFS stop records
  - hub-level PageRank aggregates nearby stop records into a station area

Outputs:
  - outputs/ttc_stop_pagerank_top5.csv
  - outputs/ttc_stop_pagerank_top5.tex
  - outputs/ttc_stop_pagerank_top5.png

Run from the project root:
    python algos/export_stop_pagerank_top5.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"
METRICS_PATH = OUTPUT_DIR / "ttc_node_metrics.csv"
TOP_N = 5


def escape_latex(value: object) -> str:
    """Escape characters that can break a LaTeX tabular."""
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def main() -> None:
    if not METRICS_PATH.exists():
        raise FileNotFoundError(f"Missing metrics file: {METRICS_PATH}")

    df = pd.read_csv(METRICS_PATH)
    if "pagerank" not in df.columns:
        raise ValueError("ttc_node_metrics.csv must contain a pagerank column")

    df = df.copy()
    df["pagerank"] = pd.to_numeric(df["pagerank"], errors="coerce").fillna(0.0)

    top = (
        df.sort_values(
            ["pagerank", "degree", "betweenness"],
            ascending=[False, False, False],
        )
        .head(TOP_N)
        .loc[:, ["stop_id", "name", "pagerank", "degree", "in_degree", "out_degree", "betweenness"]]
        .reset_index(drop=True)
    )
    top.insert(0, "rank", range(1, len(top) + 1))

    csv_path = OUTPUT_DIR / "ttc_stop_pagerank_top5.csv"
    tex_path = OUTPUT_DIR / "ttc_stop_pagerank_top5.tex"
    png_path = OUTPUT_DIR / "ttc_stop_pagerank_top5.png"

    top.to_csv(csv_path, index=False)

    with tex_path.open("w", encoding="utf-8") as handle:
        handle.write("\\begin{tabular}{r l r}\n")
        handle.write("\\toprule\n")
        handle.write("Rank & Stop Name & PageRank Score \\\\\n")
        handle.write("\\midrule\n")
        for _, row in top.loc[:, ["rank", "name", "pagerank"]].iterrows():
            handle.write(
                f"{int(row['rank'])} & {escape_latex(row['name'])} & {row['pagerank']:.10f} \\\\\n"
            )
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")

    plot_df = top.sort_values("pagerank", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.barh(
        plot_df["name"],
        plot_df["pagerank"],
        color="#7c3aed",
        edgecolor="white",
    )
    ax.set_xlabel("PageRank score")
    ax.set_ylabel("TTC stop")
    ax.set_title("Top 5 TTC Stops by PageRank")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    plt.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

    print(f"Wrote {csv_path}")
    print(f"Wrote {tex_path}")
    print(f"Wrote {png_path}")
    print()
    print(top.loc[:, ["rank", "name", "pagerank"]].to_string(index=False, formatters={"pagerank": "{:.10f}".format}))


if __name__ == "__main__":
    main()
