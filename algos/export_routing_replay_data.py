"""
Export replay data for the browser routing tab.

This script reuses the TTC graph builder and the saved output CSVs to
reconstruct the exact Dijkstra / A* paths used in the routing and
simulation outputs. It writes a small JS file that the web page can load
directly.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

import networkx as nx
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_JS = OUTPUT_DIR / "routing_replay_data.js"
ROUTING_CSV = OUTPUT_DIR / "routing_comparison.csv"
SIMULATION_CSV = OUTPUT_DIR / "simulation_results.csv"

DELAY_MULTIPLIER = 4
NUM_DELAYED_STOPS = 5
NUM_CLOSED_STOPS = 1
NUM_INTERRUPTED_EDGES = 4


sys.path.insert(0, str(Path(__file__).resolve().parent))
from graphBuilder import build_graph  # noqa: E402
from routing_detour import (
    detour_window_indices,
    get_important_stops_on_route,
    make_delay_graph,
    stitch_detour_path,
)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometres."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def astar_heuristic(graph, target):
    """Heuristic used by the saved A* runs."""

    def heuristic(node, _goal):
        try:
            node_data = graph.nodes[node]
            target_data = graph.nodes[target]
            return haversine_km(
                node_data["lat"],
                node_data["lon"],
                target_data["lat"],
                target_data["lon"],
            ) / 10000
        except KeyError:
            return 0.0

    return heuristic


def make_weight_counter():
    """Instrument edge inspections during path search."""
    counter = {"edges_checked": 0}

    def weight_fn(_u, _v, edge_data):
        counter["edges_checked"] += 1
        return edge_data.get("weight", 1)

    return weight_fn, counter


def calculate_path_cost(graph, path):
    """Sum edge weights along a path."""
    total = 0.0
    for index in range(len(path) - 1):
        total += graph[path[index]][path[index + 1]].get("weight", 1)
    return total


def run_dijkstra(graph, source, target):
    """Run Dijkstra and return the exact path plus metrics."""
    weight_fn, counter = make_weight_counter()
    path = nx.dijkstra_path(graph, source, target, weight=weight_fn)
    return {
        "path": [int(node) for node in path],
        "path_cost": round(calculate_path_cost(graph, path), 2),
        "hops": len(path) - 1,
        "edges_evaluated": counter["edges_checked"],
    }


def run_astar(graph, source, target):
    """Run A* and return the exact path plus metrics."""
    weight_fn, counter = make_weight_counter()
    path = nx.astar_path(
        graph,
        source,
        target,
        heuristic=astar_heuristic(graph, target),
        weight=weight_fn,
    )
    return {
        "path": [int(node) for node in path],
        "path_cost": round(calculate_path_cost(graph, path), 2),
        "hops": len(path) - 1,
        "edges_evaluated": counter["edges_checked"],
    }


def make_station_closure_graph(graph, baseline_path):
    """Apply the same station-closure scenario used in the saved outputs."""
    closed_graph = graph.copy()
    closed_stops = get_important_stops_on_route(graph, baseline_path, NUM_CLOSED_STOPS)
    closed_graph.remove_nodes_from(closed_stops)
    return closed_graph


def make_route_interruption_graph(graph, baseline_path):
    """Apply the same route-interruption scenario used in the saved outputs."""
    interrupted_graph = graph.copy()
    route_edges = list(zip(baseline_path, baseline_path[1:]))
    start = len(route_edges) // 2
    edges_to_remove = route_edges[start : start + NUM_INTERRUPTED_EDGES]
    interrupted_graph.remove_edges_from(edges_to_remove)
    return interrupted_graph


def run_delay_detour(graph, source, target, baseline_path, delayed_stops, algorithm):
    """Rebuild the delay scenario as a local detour around the affected window."""
    delayed_graph = make_delay_graph(graph, delayed_stops, DELAY_MULTIPLIER)
    window = detour_window_indices(baseline_path, delayed_stops)
    if window is None:
        runner = run_dijkstra if algorithm == "Dijkstra" else run_astar
        return runner(delayed_graph, source, target)

    start_idx, end_idx = window
    entry_node = baseline_path[start_idx]
    exit_node = baseline_path[end_idx]

    weight_fn, counter = make_weight_counter()
    start_time = time.perf_counter()

    try:
        if algorithm == "Dijkstra":
            detour_segment = nx.dijkstra_path(delayed_graph, entry_node, exit_node, weight=weight_fn)
        else:
            detour_segment = nx.astar_path(
                delayed_graph,
                entry_node,
                exit_node,
                heuristic=astar_heuristic(delayed_graph, exit_node),
                weight=weight_fn,
            )

        path = stitch_detour_path(baseline_path, detour_segment, start_idx, end_idx)
        runtime = time.perf_counter() - start_time
        return {
            "path": [int(node) for node in path],
            "path_cost": round(calculate_path_cost(delayed_graph, path), 2),
            "hops": len(path) - 1,
            "edges_evaluated": counter["edges_checked"],
            "runtime_s": runtime,
        }
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        runner = run_dijkstra if algorithm == "Dijkstra" else run_astar
        return runner(delayed_graph, source, target)


def node_name(graph, stop_id):
    """Return the human-readable stop name for a node."""
    return graph.nodes[stop_id].get("name", str(stop_id))


def split_semicolon(value):
    """Split a semicolon-delimited CSV field while handling blanks safely."""
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def build_routing_trials(graph):
    """Reconstruct the saved Dijkstra/A* routing trials."""
    df = pd.read_csv(ROUTING_CSV)
    trials = []

    for trial, group in df.groupby("trial", sort=True):
        row = group.iloc[0]
        source = int(row["source_id"])
        target = int(row["dest_id"])
        dijkstra = run_dijkstra(graph, source, target)
        astar = run_astar(graph, source, target)

        trials.append(
            {
                "trial": int(trial),
                "source_id": source,
                "source_name": str(row["source_name"]),
                "dest_id": target,
                "dest_name": str(row["dest_name"]),
                "same_cost": str(row["same_cost"]).strip().lower() == "true",
                "algorithms": {
                    "Dijkstra": dijkstra,
                    "A*": astar,
                },
            }
        )

    return trials


def build_simulation_scenarios(graph):
    """Reconstruct the saved disruption scenarios."""
    df = pd.read_csv(SIMULATION_CSV)
    scenarios = []

    scenario_order = ["no_disruption", "delays", "station_closure", "route_interruption"]
    for scenario_name in scenario_order:
        scenario_rows = df[df["scenario"] == scenario_name]
        if scenario_rows.empty:
            continue

        row = scenario_rows.iloc[0]
        source = int(row["source_id"])
        target = int(row["target_id"])
        baseline_path = nx.dijkstra_path(graph, source, target, weight="weight")
        delayed_stops = get_important_stops_on_route(graph, baseline_path, NUM_DELAYED_STOPS)

        if scenario_name == "no_disruption":
            scenario_graph = graph
        elif scenario_name == "delays":
            scenario_graph = make_delay_graph(graph, delayed_stops, DELAY_MULTIPLIER)
        elif scenario_name == "station_closure":
            scenario_graph = make_station_closure_graph(graph, baseline_path)
        else:
            scenario_graph = make_route_interruption_graph(graph, baseline_path)

        if scenario_name == "delays":
            algorithms = {
                "Dijkstra": run_delay_detour(graph, source, target, baseline_path, delayed_stops, "Dijkstra"),
                "A*": run_delay_detour(graph, source, target, baseline_path, delayed_stops, "A*"),
            }
            reason = (
                "Simulated service detour: edge weights near selected stops were increased "
                f"by {DELAY_MULTIPLIER}x, and the route detours around that delayed segment."
            )
        else:
            algorithms = {
                "Dijkstra": run_dijkstra(scenario_graph, source, target),
                "A*": run_astar(scenario_graph, source, target),
            }
            reason = str(row["reason"])

        scenario_entry = {
            "scenario": scenario_name,
            "reason": reason,
            "affected_stops": split_semicolon(row["affected_stops"]),
            "affected_edges": split_semicolon(row["affected_edges"]),
            "source_id": source,
            "source_name": node_name(graph, source),
            "target_id": target,
            "target_name": node_name(graph, target),
            "algorithms": algorithms,
        }
        scenarios.append(scenario_entry)

    return scenarios


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _, giant = build_graph()

    payload = {
        "routing_trials": build_routing_trials(giant),
        "simulation_scenarios": build_simulation_scenarios(giant),
    }

    OUTPUT_JS.write_text(
        "window.TTC_ROUTING_REPLAY = "
        + json.dumps(payload, ensure_ascii=True)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_JS}")


if __name__ == "__main__":
    main()
