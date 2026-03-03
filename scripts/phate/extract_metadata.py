"""
Metadata extraction for PHATE embeddings.

This module extracts metadata after PHATE embedding, including:
- Dataset statistics (n_cells, n_genes)
- Label distribution (categories, counts)
- Embedding quality metrics
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import scanpy as sc

logger = logging.getLogger(__name__)


def extract_dataset_metadata(adata: sc.AnnData, label_key: str | None = None) -> dict[str, Any]:
    """
    Extract metadata from an AnnData object.

    Args:
        adata: The AnnData object.
        label_key: The column name used for labels.

    Returns:
        Dictionary with metadata.
    """
    metadata = {
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
    }

    # Label distribution if available
    if label_key and label_key in adata.obs.columns:
        labels = adata.obs[label_key]
        value_counts = labels.value_counts()

        metadata["label_key"] = label_key
        metadata["n_categories"] = int(len(value_counts))
        metadata["n_labeled"] = int(labels.notna().sum())
        metadata["n_unlabeled"] = int(labels.isna().sum())

        # Category breakdown (all of them)
        metadata["categories"] = [
            {"name": str(cat), "count": int(count)}
            for cat, count in value_counts.items()
        ]

        # Statistics
        metadata["category_stats"] = {
            "min": int(value_counts.min()),
            "max": int(value_counts.max()),
            "mean": float(value_counts.mean()),
            "median": float(value_counts.median()),
        }

    return metadata


def extract_embedding_metrics(
    adata: sc.AnnData,
    embedding_key: str = "X_phate",
) -> dict[str, Any]:
    """
    Compute quality metrics for an embedding.

    Args:
        adata: The AnnData object with embedding.
        embedding_key: Key in adata.obsm where embedding is stored.

    Returns:
        Dictionary with metrics.
    """
    if embedding_key not in adata.obsm:
        return {"error": f"Embedding '{embedding_key}' not found"}

    embedding = adata.obsm[embedding_key]
    n_components = embedding.shape[1]

    metrics = {
        "n_components": int(n_components),
        "shape": [int(x) for x in embedding.shape],
    }

    # Per-dimension statistics
    for i in range(n_components):
        dim = embedding[:, i]
        metrics[f"dim_{i}_stats"] = {
            "min": float(dim.min()),
            "max": float(dim.max()),
            "mean": float(dim.mean()),
            "std": float(dim.std()),
        }

    # Pairwise distance statistics (for subsample if large)
    n_sample = min(1000, embedding.shape[0])
    indices = np.random.choice(embedding.shape[0], n_sample, replace=False)
    sample = embedding[indices]

    from scipy.spatial.distance import pdist

    pairwise_dists = pdist(sample)
    metrics["pairwise_distance_stats"] = {
        "min": float(pairwise_dists.min()),
        "max": float(pairwise_dists.max()),
        "mean": float(pairwise_dists.mean()),
        "median": float(np.median(pairwise_dists)),
    }

    return metrics


def compute_embedding_quality(
    adata: sc.AnnData,
    embedding_key: str = "X_phate",
    label_key: str | None = None,
) -> dict[str, Any]:
    """
    Compute embedding quality metrics.

    Args:
        adata: The AnnData object.
        embedding_key: Key for embedding in adata.obsm.
        label_key: Key for labels in adata.obs.

    Returns:
        Dictionary with quality metrics.
    """
    if embedding_key not in adata.obsm:
        return {"error": f"Embedding '{embedding_key}' not found"}

    embedding = adata.obsm[embedding_key]
    quality = {}

    # Trustworthiness (if sklearn available)
    try:
        from sklearn.neighbors import NearestNeighbors
        from sklearn.metrics import pairwise_distances

        # Sample points for efficiency
        n_sample = min(1000, embedding.shape[0])
        indices = np.random.choice(embedding.shape[0], n_sample, replace=False)

        if adata.X.shape == (adata.n_obs, adata.n_vars):
            # Compute trustworthiness in high-dimensional space
            high_d_sample = adata.X[indices].toarray() if hasattr(adata.X, "toarray") else adata.X[indices]
            low_d_sample = embedding[indices]

            # Sample for high-d distances if too large
            if high_d_sample.shape[0] > 500:
                sample_idx = np.random.choice(high_d_sample.shape[0], 500, replace=False)
                high_d_sample = high_d_sample[sample_idx]
                low_d_sample = low_d_sample[sample_idx]

            # KNN preservation
            n_neighbors = min(15, high_d_sample.shape[0] - 1)

            nn_high = NearestNeighbors(n_neighbors=n_neighbors).fit(high_d_sample)
            nn_low = NearestNeighbors(n_neighbors=n_neighbors).fit(low_d_sample)

            distances_high, indices_high = nn_high.kneighbors(high_d_sample)
            distances_low, indices_low = nn_low.kneighbors(low_d_sample)

            # Compute neighborhood preservation (for k=5, 10, 15)
            for k in [5, 10, 15]:
                if k <= n_neighbors:
                    preservation = 0.0
                    for i in range(len(indices_high)):
                        high_neighbors = set(indices_high[i, :k])
                        low_neighbors = set(indices_low[i, :k])
                        overlap = len(high_neighbors & low_neighbors)
                        preservation += overlap / k
                    preservation /= len(indices_high)
                    quality[f"neighborhood_preservation_k{k}"] = float(preservation)
    except ImportError:
        logger.debug("sklearn not available, skipping trustworthiness")
    except Exception as e:
        logger.warning(f"Failed to compute neighborhood preservation: {e}")

    # Label-based quality metrics (if labels available)
    if label_key and label_key in adata.obs.columns:
        labels = adata.obs[label_key].dropna()

        if len(labels) > 0:
            # Compute silhouette score per category (simplified)
            try:
                from sklearn.metrics import silhouette_score

                # Only compute if reasonable number of samples and categories
                unique_labels = labels.unique()
                if 2 <= len(unique_labels) <= 50 and len(labels) >= 100:
                    # Use only labeled samples
                    labeled_idx = labels.index
                    emb_labeled = embedding[labeled_idx]

                    # Convert labels to numeric
                    label_codes = labels.astype("category").cat.codes
                    if label_codes.nunique() > 1:
                        # Sample if too large
                        if len(emb_labeled) > 5000:
                            sample_idx = np.random.choice(
                                len(emb_labeled), 5000, replace=False
                            )
                            emb_labeled = emb_labeled[sample_idx]
                            label_codes = label_codes.iloc[sample_idx]

                        sil_score = silhouette_score(emb_labeled, label_codes)
                        quality["silhouette_score"] = float(sil_score)
            except Exception as e:
                logger.debug(f"Silhouette score computation failed: {e}")

    return quality


def save_metadata(
    output_path: str | Path,
    metadata: dict[str, Any],
) -> None:
    """Save metadata to JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved metadata to {output_path}")


def extract_and_save(
    adata: sc.AnnData,
    output_dir: str | Path,
    label_key: str | None = None,
    embedding_key: str = "X_phate",
) -> dict[str, Any]:
    """
    Extract all metadata and save to files.

    Args:
        adata: The AnnData object.
        output_dir: Directory to save metadata files.
        label_key: Label column name.
        embedding_key: Embedding key in adata.obsm.

    Returns:
        Combined metadata dictionary.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract all metadata
    combined = {
        "dataset": extract_dataset_metadata(adata, label_key),
        "embedding": extract_embedding_metrics(adata, embedding_key),
        "quality": compute_embedding_quality(adata, embedding_key, label_key),
    }

    # Save combined metadata
    save_metadata(output_dir / "metadata.json", combined)

    # Save individual files for convenience
    save_metadata(output_dir / "dataset_metadata.json", combined["dataset"])
    save_metadata(output_dir / "embedding_metrics.json", combined["embedding"])
    save_metadata(output_dir / "quality_metrics.json", combined["quality"])

    return combined
