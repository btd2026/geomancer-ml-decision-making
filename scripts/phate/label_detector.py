"""
Label key auto-detection for single-cell RNA-seq datasets.

This module scans H5AD files to find suitable label columns for visualization.
Common label keys include: cell_type, cell_type_ontology_term_id, cluster,
seurat_clusters, leiden, louvain, etc.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import scanpy as sc

logger = logging.getLogger(__name__)

# Common label column names in single-cell data, ordered by priority
COMMON_LABEL_KEYS = [
    "cell_type",
    "cell_type_ontology_term_id",
    "cluster",
    "clusters",
    "seurat_clusters",
    "leiden",
    "louvain",
    "cell_type_authors",
    "assigned_cell_type",
    "inferred_cell_type",
    "cell_type_broad",
    "major_cell_type",
    "cell_subtype",
    "annotation",
    "labels",
    "class",
    "cell_class",
]


def detect_label_key(
    adata: sc.AnnData,
    preferred_keys: list[str] | None = None,
    min_categories: int = 2,
    max_categories: int = 500,
    min_cells_per_category: int = 5,
) -> str | None:
    """
    Detect the best label key from an AnnData object.

    Args:
        adata: The AnnData object to scan.
        preferred_keys: List of keys to check first (before COMMON_LABEL_KEYS).
        min_categories: Minimum number of unique categories required.
        max_categories: Maximum number of unique categories allowed.
        min_cells_per_category: Minimum cells required per category.

    Returns:
        The name of the best label key, or None if no suitable key found.
    """
    # Combine preferred keys with common keys, removing duplicates
    search_keys = (preferred_keys or []) + COMMON_LABEL_KEYS
    seen = set()
    unique_keys = [k for k in search_keys if not (k in seen or seen.add(k))]

    # Check obs columns first
    for key in unique_keys:
        if key not in adata.obs.columns:
            continue

        labels = adata.obs[key]
        unique_values = labels.unique()

        # Skip if too few or too many categories
        if len(unique_values) < min_categories or len(unique_values) > max_categories:
            continue

        # Skip if continuous-looking data (too many unique numeric values)
        if pd.api.types.is_numeric_dtype(labels):
            if len(unique_values) > 50:
                continue

        # Check minimum cells per category
        value_counts = labels.value_counts()
        if value_counts.min() < min_cells_per_category:
            continue

        # This key looks good
        return key

    # If no common keys found, look for any categorical column
    for col in adata.obs.columns:
        if col in unique_keys:
            continue  # Already checked

        labels = adata.obs[col]
        unique_values = labels.unique()

        if len(unique_values) < min_categories or len(unique_values) > max_categories:
            continue

        # Check for categorical-like data
        if pd.api.types.is_numeric_dtype(labels):
            if len(unique_values) > 50:
                continue

        value_counts = labels.value_counts()
        if value_counts.min() < min_cells_per_category:
            continue

        return col

    return None


def get_label_summary(adata: sc.AnnData, label_key: str) -> dict[str, Any]:
    """
    Get summary statistics for a label key.

    Args:
        adata: The AnnData object.
        label_key: The column name in adata.obs.

    Returns:
        Dictionary with summary statistics.
    """
    labels = adata.obs[label_key]
    value_counts = labels.value_counts()

    return {
        "key": label_key,
        "n_categories": len(value_counts),
        "n_labeled": labels.notna().sum(),
        "n_unlabeled": labels.isna().sum(),
        "top_categories": value_counts.head(10).to_dict(),
        "min_cells_per_category": value_counts.min(),
        "max_cells_per_category": value_counts.max(),
        "mean_cells_per_category": value_counts.mean(),
    }


def preview_labels(
    h5ad_path: str | Path,
    label_key: str | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    """
    Preview labels from an H5AD file without loading full data.

    Args:
        h5ad_path: Path to the H5AD file.
        label_key: Specific key to preview. If None, auto-detects.
        top_n: Number of top categories to show.

    Returns:
        Dictionary with preview information.
    """
    import pandas as pd  # Import here to avoid top-level dependency

    # Read just the metadata (obs) without loading full matrix
    adata = sc.read_h5ad(h5ad_path, backed="r")

    result = {
        "path": str(h5ad_path),
        "n_obs": adata.n_obs,
        "n_vars": adata.n_vars,
        "available_keys": list(adata.obs.columns),
    }

    if label_key and label_key not in adata.obs.columns:
        result["error"] = f"Label key '{label_key}' not found in obs"
        return result

    # Auto-detect if not specified
    detected_key = label_key or detect_label_key(adata)

    if detected_key:
        summary = get_label_summary(adata, detected_key)
        result.update(summary)
        result["detected_key"] = detected_key

        # Show category distribution preview
        labels = adata.obs[detected_key]
        value_counts = labels.value_counts()

        result["categories_preview"] = [
            {"name": str(cat), "count": int(count)}
            for cat, count in value_counts.head(top_n).items()
        ]
    else:
        result["detected_key"] = None
        result["error"] = "No suitable label key found"

    return result


def batch_detect_labels(
    h5ad_paths: list[str | Path],
    preferred_keys: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Detect label keys for multiple H5AD files.

    Args:
        h5ad_paths: List of paths to H5AD files.
        preferred_keys: Keys to check first.

    Returns:
        Dictionary mapping file paths to detection results.
    """
    results = {}

    for path in h5ad_paths:
        try:
            result = preview_labels(path, label_key=None)
            results[str(path)] = result
        except Exception as e:
            logger.warning(f"Failed to process {path}: {e}")
            results[str(path)] = {"error": str(e)}

    return results


# Import pandas at module level for dtype checking
try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore
