"""
Export a top-10 ranking of historical transit hubs by PageRank.

Method:
  1. Read the stop-level PageRank table from outputs/ttc_node_metrics.csv.
  2. Join it with GTFS stop coordinates by stop_id.
  3. For each historical hub in dataset/completegtfs/type_ii_major_hubs_collapsed.csv,
     sum PageRank for all stop records within a 450 m radius of the hub center.
  4. Sort hubs by the aggregated PageRank score and write report-ready outputs.

Outputs:
  - outputs/historical_hub_pagerank_top10.csv
  - outputs/historical_hub_pagerank_top10.tex
  - outputs/historical_hub_pagerank_top10.png

Run from the project root:
    python algos/export_historical_hub_pagerank.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"
METRICS_PATH = OUTPUT_DIR / "ttc_node_metrics.csv"
STOPS_PATH = ROOT / "dataset" / "completegtfs" / "stops.csv"
HUBS_PATH = ROOT / "dataset" / "completegtfs" / "type_ii_major_hubs_collapsed.csv"
RADIUS_METERS = 450
TOP_N = 10


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    earth_radius_m = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def escape_latex(value: object) -> str:
    """Escape the handful of characters that can break a LaTeX tabular."""
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
    if not STOPS_PATH.exists():
        raise FileNotFoundError(f"Missing GTFS stops file: {STOPS_PATH}")
    if not HUBS_PATH.exists():
        raise FileNotFoundError(f"Missing historical hubs file: {HUBS_PATH}")

    metrics = pd.read_csv(METRICS_PATH)
    stops = pd.read_csv(STOPS_PATH)
    hubs = pd.read_csv(HUBS_PATH)

    metrics = metrics.copy()
    metrics["pagerank"] = pd.to_numeric(metrics["pagerank"], errors="coerce").fillna(0.0)

    # Attach coordinates from GTFS so we can do a spatial aggregation around each hub.
    stop_coords = stops.loc[:, ["stop_id", "stop_lat", "stop_lon"]].copy()
    stop_coords["stop_lat"] = pd.to_numeric(stop_coords["stop_lat"], errors="coerce")
    stop_coords["stop_lon"] = pd.to_numeric(stop_coords["stop_lon"], errors="coerce")
    metrics = metrics.merge(stop_coords, on="stop_id", how="left")
    metrics = metrics.dropna(subset=["stop_lat", "stop_lon"]).reset_index(drop=True)

    hubs = hubs.copy()
    hubs["stop_lat"] = pd.to_numeric(hubs["stop_lat"], errors="coerce")
    hubs["stop_lon"] = pd.to_numeric(hubs["stop_lon"], errors="coerce")
    hubs["Degree"] = pd.to_numeric(hubs["Degree"], errors="coerce")
    hubs["Closeness"] = pd.to_numeric(hubs["Closeness"], errors="coerce")
    hubs["Betweenness"] = pd.to_numeric(hubs["Betweenness"], errors="coerce")
    hubs["platform_stop_count"] = pd.to_numeric(hubs["platform_stop_count"], errors="coerce")

    rows = []
    for _, hub in hubs.iterrows():
        hub_lat = hub["stop_lat"]
        hub_lon = hub["stop_lon"]
        if pd.isna(hub_lat) or pd.isna(hub_lon):
            continue

        within = []
        for _, stop in metrics.iterrows():
            if haversine_m(hub_lat, hub_lon, stop["stop_lat"], stop["stop_lon"]) <= RADIUS_METERS:
                within.append(stop)

        within_df = pd.DataFrame(within)
        rows.append(
            {
                "station_name": hub["stop_name"],
                "pagerank_score": float(within_df["pagerank"].sum()) if not within_df.empty else 0.0,
                "matched_nodes": int(len(within_df)),
                "degree_centrality": float(hub["Degree"]) if not pd.isna(hub["Degree"]) else 0.0,
                "closeness": float(hub["Closeness"]) if not pd.isna(hub["Closeness"]) else 0.0,
                "betweenness": float(hub["Betweenness"]) if not pd.isna(hub["Betweenness"]) else 0.0,
                "platform_stop_count": int(hub["platform_stop_count"]) if not pd.isna(hub["platform_stop_count"]) else 0,
            }
        )

    ranked = (
        pd.DataFrame(rows)
        .sort_values(
            ["pagerank_score", "degree_centrality", "platform_stop_count"],
            ascending=[False, False, False],
        )
        .reset_index(drop=True)
    )
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    top = ranked.head(TOP_N).copy()

    csv_path = OUTPUT_DIR / "historical_hub_pagerank_top10.csv"
    tex_path = OUTPUT_DIR / "historical_hub_pagerank_top10.tex"
    png_path = OUTPUT_DIR / "historical_hub_pagerank_top10.png"

    top.to_csv(csv_path, index=False)
    with tex_path.open("w", encoding="utf-8") as handle:
        handle.write("\\begin{tabular}{r l r}\n")
        handle.write("\\toprule\n")
        handle.write("Rank & Station Name & PageRank Score \\\\\n")
        handle.write("\\midrule\n")
        for _, row in top.loc[:, ["rank", "station_name", "pagerank_score"]].iterrows():
            handle.write(
                f"{int(row['rank'])} & {escape_latex(row['station_name'])} & {row['pagerank_score']:.10f} \\\\\n"
            )
        handle.write("\\bottomrule\n")
        handle.write("\\end{tabular}\n")

    plot_df = top.sort_values("pagerank_score", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.barh(
        plot_df["station_name"],
        plot_df["pagerank_score"],
        color="#0f766e",
        edgecolor="white",
    )
    ax.set_xlabel("PageRank score")
    ax.set_ylabel("Historical transit hub")
    ax.set_title(f"Top {TOP_N} Historical Transit Hubs by PageRank")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    plt.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

    print(f"Wrote {csv_path}")
    print(f"Wrote {tex_path}")
    print(f"Wrote {png_path}")
    print()
    print(top.loc[:, ["rank", "station_name", "pagerank_score"]].to_string(index=False, formatters={"pagerank_score": "{:.10f}".format}))
    print()
    print(f"Radius used for aggregation: {RADIUS_METERS} m")


if __name__ == "__main__":
    main()
