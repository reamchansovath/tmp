# ── network_graph/pipeline/graph_builder.py ──────────────────────────────────
# Utility functions for building adjacency dictionaries from edge dataframes.
#
# NOTE: Recipe 1 Cell 8 builds RSME adjacency inline for performance.
# These functions are kept as testable utilities for any future recipe
# that needs to rebuild adjacency outside the main pipeline.

import pandas as pd
from typing import Dict, List

from ..sources.base_source import BaseSource as _BS
_INVALID_IDS = _BS.INVALID_IDS  # local alias; canonical set lives on BaseSource


def build_adjacency_from_edges(edges_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Build an undirected adjacency dictionary from an edge dataframe.

    Parameters
    ----------
    edges_df : pd.DataFrame
        Edge dataframe with SOURCE_UEN and TARGET_UEN columns.

    Returns
    -------
    dict
        Deduplicated undirected adjacency {uen: [neighbor_uens]}
    """
    adjacency: Dict[str, List[str]] = {}

    for r in edges_df[['SOURCE_UEN', 'TARGET_UEN']].to_dict('records'):
        src = str(r['SOURCE_UEN']).strip()
        tgt = str(r['TARGET_UEN']).strip()

        if src in _INVALID_IDS or tgt in _INVALID_IDS or src == tgt:
            continue

        if src not in adjacency: adjacency[src] = []
        if tgt not in adjacency: adjacency[tgt] = []

        adjacency[src].append(tgt)
        adjacency[tgt].append(src)

    return {k: list(set(v)) for k, v in adjacency.items()}


def calculate_degree_map(adjacency: Dict[str, List[str]]) -> Dict[str, int]:
    """
    Calculate degree map from adjacency dictionary.

    Parameters
    ----------
    adjacency : dict
        Adjacency dictionary {uen: [neighbor_uens]}

    Returns
    -------
    dict
        Degree map {uen: degree_count}
    """
    return {k: len(v) for k, v in adjacency.items()}
