#!/usr/bin/env python3
"""
Generate ManyLatents experiment configs for preprocessed datasets.

Scans the preprocessed directory and generates:
1. Experiment YAML configs for ManyLatents
2. phate_experiments.yaml for SLURM array jobs
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

import scanpy as sc
import numpy as np


def get_categorical_columns(adata: sc.AnnData) -> List[str]:
    """Get all categorical columns in obs."""
    import pandas as pd

    categorical = []
    for col in adata.obs.columns:
        col_data = adata.obs[col]
        if isinstance(col_data.dtype, pd.CategoricalDtype):
            categorical.append(col)
        elif col_data.dtype == 'object':
            n_unique = col_data.nunique()
            if n_unique < min(100, len(adata) / 10):
                categorical.append(col)
    return categorical


def count_categories(adata: sc.AnnData, col: str) -> int:
    """Count unique categories in a column."""
    col_data = adata.obs[col]
    if isinstance(col_data.dtype, pd.CategoricalDtype):
        return len(col_data.cat.categories)
    return col_data.nunique()


# Priority columns for auto-suggesting label keys
PRIORITY_COLUMNS = {
    "condition": ["disease", "Disease", "disease_status", "condition", "Condition",
                  "health_status", "status", "Status", "COVID_status", "covid_status"],
    "stages": ["development_stage", "developmental_stage", "stage", "Stage",
               "disease_stage", "tumor_stage", "cancer_stage", "lineage", "Lineage"],
    "celltype": ["cell_type", "celltype", "CellType", "author_cell_type",
                 "major_celltype", "broad_cell_type"],
    "time": ["Day", "day", "days", "timepoint", "time_point", "TimePoint", "time",
             "DayFactor", "day_factor"],
    "cluster": ["cluster", "Cluster", "leiden", "louvain", "seurat_clusters"],
}


def suggest_label_key(adata: sc.AnnData, min_categories: int = 2,
                      max_categories: int = 100) -> Optional[str]:
    """Suggest the best label key for visualization."""
    import pandas as pd

    categorical_cols = get_categorical_columns(adata)

    for category, columns in PRIORITY_COLUMNS.items():
        for col in columns:
            if col in categorical_cols:
                n_cats = count_categories(adata, col)
                if min_categories <= n_cats <= max_categories:
                    return col

    for col in categorical_cols:
        n_cats = count_categories(adata, col)
        if min_categories <= n_cats <= max_categories:
            return col

    return None


def analyze_dataset(h5ad_path: Path) -> Dict[str, Any]:
    """Analyze a preprocessed H5AD file to extract metadata."""
    try:
        adata = sc.read_h5ad(h5ad_path)

        # Get experiment name from filename
        exp_name = h5ad_path.stem

        # Suggest label key
        label_key = suggest_label_key(adata)

        if label_key is None:
            # Fallback to first usable column
            import pandas as pd
            for col in adata.obs.columns:
                if adata.obs[col].dtype == 'object' or isinstance(adata.obs[col].dtype, pd.CategoricalDtype):
                    label_key = col
                    break

        n_categories = count_categories(adata, label_key) if label_key else 0

        return {
            "name": exp_name,
            "h5ad_file": h5ad_path.name,
            "adata_path": str(h5ad_path),
            "label_key": label_key,
            "n_categories": n_categories,
            "n_cells": adata.n_obs,
            "n_genes": adata.n_vars,
        }
    except Exception as e:
        print(f"Warning: Could not analyze {h5ad_path.name}: {e}")
        return None


def generate_cellxgene_experiments_yaml(
    datasets: List[Dict[str, Any]],
    output_path: Path,
):
    """Generate phate_experiments.yaml for ManyLatents SLURM jobs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write("experiments:\n")
        for ds in datasets:
            f.write(f"- algorithm: phate\n")
            f.write(f"  config_path: /home/btd8/manylatents/configs/experiment/cellxgene/{ds['name']}.yaml\n")
            f.write(f"  h5ad_file: {ds['h5ad_file']}\n")
            f.write(f"  label_key: {ds['label_key']}\n")
            f.write(f"  name: {ds['name']}\n")
            f.write("\n")

    print(f"Generated {output_path}")


def generate_experiment_configs(
    datasets: List[Dict[str, Any]],
    output_dir: Path,
    preprocessed_dir: Path,
):
    """Generate individual experiment YAML configs for ManyLatents."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for ds in datasets:
        exp_path = output_dir / f"{ds['name']}.yaml"

        with open(exp_path, 'w') as f:
            f.write("# @package _global_\n")
            f.write(f"name: phate_{ds['name']}\n\n")
            f.write("defaults:\n")
            f.write("  - override /algorithms/latent: phate\n")
            f.write("  - override /data: cellxgene_dataset\n")
            f.write("  - override /callbacks/embedding: default\n")
            f.write("  - override /metrics: test_metric\n\n")
            f.write("seed: 42\n")
            f.write("project: phate_cellxgene\n\n")
            f.write("data:\n")
            f.write(f"  adata_path: {ds['adata_path']}\n")
            f.write(f"  label_key: {ds['label_key']}\n\n")
            f.write("algorithms:\n")
            f.write("  latent:\n")
            f.write("    n_components: 2\n")
            f.write("    knn: 100\n")
            f.write("    t: 12\n")
            f.write("    decay: 60\n")

    print(f"Generated {len(datasets)} experiment configs in {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate ManyLatents experiment configs from preprocessed data"
    )
    parser.add_argument(
        "--preprocessed-dir",
        type=str,
        default="/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/preprocessed",
        help="Directory with preprocessed H5AD files"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/home/btd8/manylatents/configs/experiment/cellxgene",
        help="Output directory for experiment configs"
    )
    parser.add_argument(
        "--experiments-list",
        type=str,
        default="/home/btd8/manylatents/phate_experiments.yaml",
        help="Output path for phate_experiments.yaml"
    )

    args = parser.parse_args()

    preprocessed_dir = Path(args.preprocessed_dir)
    output_dir = Path(args.output_dir)
    experiments_list = Path(args.experiments_list)

    if not preprocessed_dir.exists():
        print(f"Error: Preprocessed directory not found: {preprocessed_dir}")
        print("Please run the preprocessing job first.")
        sys.exit(1)

    # Find all H5AD files
    h5ad_files = sorted(list(preprocessed_dir.glob("*.h5ad")))

    if not h5ad_files:
        print(f"Error: No H5AD files found in {preprocessed_dir}")
        sys.exit(1)

    print(f"Found {len(h5ad_files)} preprocessed datasets")
    print("=" * 60)

    # Analyze all datasets
    datasets = []
    for h5ad_path in h5ad_files:
        metadata = analyze_dataset(h5ad_path)
        if metadata:
            datasets.append(metadata)
            print(f"  {metadata['name']}: {metadata['n_cells']:,} cells, "
                  f"label={metadata['label_key']} ({metadata['n_categories']} categories)")

    if not datasets:
        print("Error: No valid datasets found")
        sys.exit(1)

    print("=" * 60)
    print(f"Analyzed {len(datasets)} datasets")

    # Generate outputs
    print("\nGenerating outputs...")

    generate_cellxgene_experiments_yaml(datasets, experiments_list)
    generate_experiment_configs(datasets, output_dir, preprocessed_dir)

    # Save metadata JSON
    metadata_path = preprocessed_dir / "datasets_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump({
            "total_datasets": len(datasets),
            "datasets": datasets,
        }, f, indent=2)
    print(f"Saved metadata to: {metadata_path}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
