#!/usr/bin/env python3
"""
PHATE runner with organized output structure and WandB logging.
Accepts a JSON configuration file for run parameters.

Output structure:
output_dir/
  dataset_name/
    metadata.json           # Dataset-level metadata (cells, genes, description)
    runs/
      run_id/
        metadata.json       # Run-level metadata (PHATE params, label key)
        config.json         # Full configuration used
        phate_plot.png      # PHATE visualization with colors
        phate_plot_legend.png  # Color legend
        embedding.csv       # PHATE coordinates
        colors.json         # Color mapping for each label
        manual_classification.json  # For user annotations
"""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
import scanpy as sc
import phate
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import wandb

# Use non-interactive backend for SLURM
matplotlib.use('Agg')

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Color palette for labels (20 distinct colors)
COLOR_PALETTE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
    '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'
]


def get_label_colors(labels: pd.Series) -> Dict[str, str]:
    """Generate consistent colors for labels."""
    unique_labels = labels.unique()
    colors = {}
    for i, label in enumerate(unique_labels):
        colors[str(label)] = COLOR_PALETTE[i % len(COLOR_PALETTE)]
    return colors


def create_phate_plot(
    embedding: np.ndarray,
    labels: pd.Series,
    colors: Dict[str, str],
    output_path: Path,
    title: str = "PHATE",
) -> None:
    """Create PHATE scatter plot with colors by label."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot each label group with its color
    for label, color in colors.items():
        mask = labels == label
        ax.scatter(
            embedding[mask, 0],
            embedding[mask, 1],
            c=color,
            label=label,
            alpha=0.6,
            s=10 if len(embedding) > 10000 else 20,
            edgecolors='none',
        )

    ax.set_xlabel('PHATE 1')
    ax.set_ylabel('PHATE 2')
    ax.set_title(title)
    # No legend in main plot - legend is saved separately as phate_plot_legend.png

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def create_legend_plot(
    colors: Dict[str, str],
    label_counts: pd.Series,
    output_path: Path,
) -> None:
    """Create a separate legend plot."""
    fig, ax = plt.subplots(figsize=(6, max(4, len(colors) * 0.3)))

    labels = list(colors.keys())
    color_values = [colors[l] for l in labels]
    counts = [label_counts[l] for l in labels]

    # Create legend entries
    for i, (label, color, count) in enumerate(zip(labels, color_values, counts)):
        ax.scatter([], [], c=color, label=f'{label} (n={count})')

    ax.axis('off')
    ax.legend(
        loc='center',
        fontsize=10,
        frameon=True,
        facecolor='white',
        edgecolor='gray',
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def detect_label_key(adata: sc.AnnData) -> str | None:
    """Auto-detect a suitable label key from adata.obs."""
    common_keys = [
        "cell_type", "cell_type_ontology_term_id", "cluster", "clusters",
        "seurat_clusters", "leiden", "louvain", "SampleID",
    ]
    for key in common_keys:
        if key in adata.obs.columns:
            labels = adata.obs[key]
            unique = labels.unique()
            if 2 <= len(unique) <= 500:
                value_counts = labels.value_counts()
                if value_counts.min() >= 5:
                    return key

    # Look for any suitable categorical column
    for col in adata.obs.columns:
        if col in common_keys:
            continue
        labels = adata.obs[col]
        unique = labels.unique()
        if 2 <= len(unique) <= 500:
            value_counts = labels.value_counts()
            if value_counts.min() >= 5:
                return col
    return None


def load_run_config(config_path: str) -> Dict[str, Any]:
    """Load run configuration from JSON file."""
    with open(config_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Run PHATE with organized output from JSON config")
    parser.add_argument("config_json", type=str, help="Path to JSON config file with run parameters")

    args = parser.parse_args()

    # Load configuration from JSON
    config = load_run_config(args.config_json)

    # Extract parameters from config
    h5ad_path = config["h5ad_path"]
    dataset_name = config["dataset_name"]
    output_base_dir = config["output_base_dir"]
    run_name = config.get("run_name", "default")
    description = config.get("description", "")
    label_key = config.get("label_key", "auto")

    # PHATE parameters
    phate_params = config.get("phate_params", {
        "n_components": 2,
        "knn": 30,
        "t": 10,
        "decay": 60,
        "seed": 42,
    })

    # WandB configuration
    wandb_config = config.get("wandb", {
        "entity": "cesar-valdez-mcgill-university",
        "project": "manylatent-2026-brian",
    })

    # Create output directory structure
    output_base = Path(output_base_dir)
    dataset_dir = output_base / dataset_name
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # Dataset-level metadata (shared across runs)
    dataset_metadata_path = dataset_dir / "metadata.json"

    # Run directory
    run_id = f"{run_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = dataset_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Initialize WandB
    wandb.init(
        entity=wandb_config.get("entity", "cesar-valdez-mcgill-university"),
        project=wandb_config.get("project", "manylatent-2026-brian"),
        name=f"{dataset_name}_{run_name}",
        config={
            **config,
            "run_id": run_id,
        },
        tags=["phate", "single-cell", "h5ad"],
    )

    try:
        logger.info(f"Loading H5AD from {h5ad_path}")
        adata = sc.read_h5ad(h5ad_path)

        n_obs, n_vars = adata.n_obs, adata.n_vars
        logger.info(f"Data: {n_obs} cells x {n_vars} genes")

        # Save dataset-level metadata (if not exists)
        if not dataset_metadata_path.exists():
            dataset_metadata = {
                "name": dataset_name,
                "description": description,
                "h5ad_path": h5ad_path,
                "n_obs": int(n_obs),
                "n_vars": int(n_vars),
                "created_at": datetime.now().isoformat(),
            }
            with open(dataset_metadata_path, 'w') as f:
                json.dump(dataset_metadata, f, indent=2)

        # Detect label key
        if label_key == "auto":
            label_key = detect_label_key(adata)
            if label_key:
                logger.info(f"Auto-detected label key: {label_key}")
            else:
                logger.warning("No suitable label key found")
                label_key = None

        # Get labels and colors
        labels = None
        label_colors = {}
        label_counts = None

        if label_key and label_key in adata.obs.columns:
            labels = adata.obs[label_key]
            label_counts = labels.value_counts()
            label_colors = get_label_colors(labels)
            n_categories = len(label_counts)
            logger.info(f"Label key: {label_key}, Categories: {n_categories}")

            # Save colors mapping
            colors_path = run_dir / "colors.json"
            with open(colors_path, 'w') as f:
                json.dump({
                    "label_key": label_key,
                    "colors": {str(k): v for k, v in label_colors.items()},
                    "n_categories": n_categories,
                }, f, indent=2)

        # Run PHATE
        n_pca = phate_params.get("n_pca", None)
        logger.info(f"Running PHATE: knn={phate_params['knn']}, t={phate_params['t']}, decay={phate_params['decay']}, n_pca={n_pca}")
        phate_op = phate.PHATE(
            n_components=phate_params["n_components"],
            knn=phate_params["knn"],
            t=phate_params["t"],
            decay=phate_params["decay"],
            random_state=phate_params["seed"],
            n_jobs=-1,
            n_pca=n_pca,
        )

        # Handle sparse matrices
        if hasattr(adata.X, "toarray"):
            X = adata.X.toarray()
        else:
            X = adata.X

        embedding = phate_op.fit_transform(X)
        logger.info(f"PHATE embedding shape: {embedding.shape}")

        # Save embedding
        embedding_df = pd.DataFrame(
            embedding,
            columns=[f"PHATE_{i}" for i in range(embedding.shape[1])],
            index=adata.obs_names,
        )
        embedding_path = run_dir / "embedding.csv"
        embedding_df.to_csv(embedding_path)
        logger.info(f"Saved embedding to {embedding_path}")

        # Save labels separately (for memory-efficient regeneration)
        if labels is not None:
            labels_path = run_dir / "labels.csv"
            labels_df = pd.DataFrame({label_key: labels}, index=adata.obs_names)
            labels_df.to_csv(labels_path)
            logger.info(f"Saved labels to {labels_path}")

        # Create plots
        if labels is not None:
            plot_path = run_dir / "phate_plot.png"
            create_phate_plot(
                embedding,
                labels,
                label_colors,
                plot_path,
                title=f"{dataset_name} - {label_key}",
            )
            logger.info(f"Saved plot to {plot_path}")

            legend_path = run_dir / "phate_plot_legend.png"
            create_legend_plot(label_colors, label_counts, legend_path)
            logger.info(f"Saved legend to {legend_path}")

            # Log plot to WandB
            wandb.log({
                "phate_plot": wandb.Image(str(plot_path)),
                "phate_legend": wandb.Image(str(legend_path)),
            })

        # Save run metadata
        run_metadata = {
            "run_id": run_id,
            "dataset_name": dataset_name,
            "label_key": label_key,
            "n_categories": n_categories if labels is not None else 0,
            "phate_params": phate_params,
            "timestamp": datetime.now().isoformat(),
        }

        run_metadata_path = run_dir / "metadata.json"
        with open(run_metadata_path, 'w') as f:
            json.dump(run_metadata, f, indent=2)

        # Save full config
        config_save_path = run_dir / "config.json"
        with open(config_save_path, 'w') as f:
            json.dump(config, f, indent=2, default=str)

        # Create empty manual classification file
        manual_class_path = run_dir / "manual_classification.json"
        with open(manual_class_path, 'w') as f:
            json.dump({
                "manual_annotations": {},
                "quality_issues": [],
                "notes": "",
            }, f, indent=2)

        # Log to WandB
        wandb.log({
            "n_cells": n_obs,
            "n_genes": n_vars,
            "n_categories": n_categories if labels is not None else 0,
            "embedding_dim": embedding.shape[1],
            "label_key": label_key,
        })

        # Upload embedding as artifact
        artifact = wandb.Artifact(name=f"{dataset_name}_{run_id}", type="phate_run")
        artifact.add_file(str(embedding_path))
        artifact.add_file(str(run_metadata_path))
        if labels is not None:
            artifact.add_file(str(plot_path))
            artifact.add_file(str(legend_path))
        wandb.log_artifact(artifact)

        logger.info(f"Run complete: {run_dir}")

    finally:
        wandb.finish()


if __name__ == "__main__":
    main()
