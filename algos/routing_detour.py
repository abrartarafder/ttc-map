"""Shared helpers for localized TTC detour routing."""

from __future__ import annotations


def get_important_stops_on_route(graph, path, count):
    """Choose the most connected intermediate stops on a baseline path."""
    middle_stops = path[1:-1]
    ranked_stops = sorted(middle_stops, key=lambda stop: graph.degree(stop), reverse=True)
    return ranked_stops[:count]


def make_delay_graph(graph, delayed_stops, delay_multiplier):
    """Return a copy of the graph with delay penalties applied near selected stops."""
    delayed_graph = graph.copy()
    for u, v, edge_data in delayed_graph.edges(data=True):
        if u in delayed_stops or v in delayed_stops:
            edge_data["weight"] = edge_data.get("weight", 1) * delay_multiplier
    return delayed_graph


def detour_window_indices(path, affected_stops):
    """
    Find the smallest baseline-path window that surrounds the delayed segment.

    The detour starts one node before the first affected stop and rejoins one
    node after the last affected stop, so the reroute stays local instead of
    recomputing the whole trip.
    """
    affected_indices = [index for index, stop in enumerate(path) if stop in affected_stops]
    if not affected_indices:
        return None

    start_idx = max(0, min(affected_indices) - 1)
    end_idx = min(len(path) - 1, max(affected_indices) + 1)
    if start_idx >= end_idx:
        return None
    return start_idx, end_idx


def stitch_detour_path(baseline_path, detour_segment, start_idx, end_idx):
    """Combine the untouched baseline prefix/suffix with the detour segment."""
    return baseline_path[: start_idx + 1] + detour_segment[1:-1] + baseline_path[end_idx:]
