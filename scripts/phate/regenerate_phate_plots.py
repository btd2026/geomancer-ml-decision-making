#!/usr/bin/env python3
"""
Regenerate PHATE plots without legends.

This script takes existing PHATE embeddings and regenerates the plots
with legend=False.

Usage:
    # Preview what will be regenerated
    python scripts/phate/regenerate_phate_plots.py --preview

    # Regenerate plots (uses existing embeddings, just re-plots)
    python scripts/phate/regenerate_phate_plots.py --run

    # Submit to SLURM
    python scripts/phate/regenerate_phate_plots.py --generate-slurm
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def find_embedding_dirs(results_dir: Path) -> list[dict]:
    """Find all directories with PHATE embeddings."""
    dirs = []
    for subdir in sorted(results_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith('.'):
            continue

        # Find embedding CSV files
        csv_files = list(subdir.glob("embeddings_*.csv"))
        if csv_files:
            dirs.append({
                "name": subdir.name,
                "dir": str(subdir),
                "embedding_file": str(csv_files[0]),
            })
    return dirs


def load_embeddings(embedding_path: Path) -> np.ndarray:
    """Load embeddings from CSV."""
    df = pd.read_csv(embedding_path)
    return df.values.astype(np.float64)


def load_colors(dir_path: Path) -> tuple[dict, str]:
    """Load colors.json if it exists."""
    colors_path = dir_path / "colors.json"
    if colors_path.exists():
        with open(colors_path) as f:
            data = json.load(f)
        return data.get("colors", {}), data.get("label_key", "unknown")
    return {}, "unknown"


def load_labels(dir_path: Path, h5ad_path: str, label_key: str) -> np.ndarray:
    """Load labels from the original h5ad file."""
    try:
        import scanpy as sc
        adata = sc.read_h5ad(h5ad_path)
        if label_key in adata.obs.columns:
            return adata.obs[label_key].values
    except Exception as e:
        logger.warning(f"Could not load labels: {e}")
    return None


def regenerate_plot(
    embeddings: np.ndarray,
    labels: np.ndarray,
    colors: dict,
    output_path: Path,
    figsize: tuple = (8, 6),
) -> None:
    """Regenerate PHATE plot without legend."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=figsize)

    if labels is not None and colors:
        # Map labels to colors
        unique_labels = sorted(set(labels))
        default_color = "#808080"

        for lbl in unique_labels:
            mask = labels == lbl
            color = colors.get(str(lbl), colors.get(lbl, default_color))
            ax.scatter(
                embeddings[mask, 0],
                embeddings[mask, 1],
                c=color,
                s=8,
                alpha=0.8,
                label=str(lbl),
            )
        # No legend!
    else:
        ax.scatter(
            embeddings[:, 0],
            embeddings[:, 1],
            s=8,
            alpha=0.8,
        )

    ax.set_xlabel("Dim 1", fontsize=12)
    ax.set_ylabel("Dim 2", fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])

    plt.savefig(output_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def process_single_dataset(dataset_info: dict, dry_run: bool = False) -> dict:
    """Process a single dataset."""
    name = dataset_info["name"]
    dir_path = Path(dataset_info["dir"])
    embedding_path = Path(dataset_info["embedding_file"])

    logger.info(f"Processing: {name}")

    if dry_run:
        return {"name": name, "status": "skipped", "reason": "dry_run"}

    # Load embeddings
    try:
        embeddings = load_embeddings(embedding_path)
    except Exception as e:
        logger.error(f"  Failed to load embeddings: {e}")
        return {"name": name, "status": "error", "error": str(e)}

    # Load colors
    colors, label_key = load_colors(dir_path)

    # Try to load labels from h5ad
    labels = None
    hydra_config = dir_path / ".hydra" / "config.yaml"
    if hydra_config.exists():
        import yaml
        with open(hydra_config) as f:
            config = yaml.safe_load(f)
        h5ad_path = config.get("data", {}).get("adata_path", "")
        if h5ad_path and os.path.exists(h5ad_path):
            labels = load_labels(dir_path, h5ad_path, label_key)

    # Find and remove old plot files
    old_plots = list(dir_path.glob("embedding_plot_*.png"))
    for old_plot in old_plots:
        logger.info(f"  Removing old plot: {old_plot}")
        os.remove(old_plot)

    # Generate new plot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"embedding_plot_phate_k100_{name}_{timestamp}.png"
    output_path = dir_path / output_filename

    regenerate_plot(embeddings, labels, colors, output_path)

    return {"name": name, "status": "success", "output": str(output_path)}


def main():
    parser = argparse.ArgumentParser(description="Regenerate PHATE plots without legends")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results"),
        help="Directory containing PHATE results",
    )
    parser.add_argument("--preview", action="store_true", help="Preview what will be processed")
    parser.add_argument("--run", action="store_true", help="Actually regenerate plots")
    parser.add_argument("--generate-slurm", action="store_true", help="Generate SLURM script")
    parser.add_argument("--dataset", type=str, help="Process specific dataset only")

    args = parser.parse_args()

    datasets = find_embedding_dirs(args.results_dir)
    print(f"Found {len(datasets)} datasets with embeddings")

    if args.preview:
        for i, ds in enumerate(datasets[:10]):
            print(f"  {i+1}. {ds['name']}")
        if len(datasets) > 10:
            print(f"  ... and {len(datasets) - 10} more")
        return

    if args.generate_slurm:
        script = f"""#!/bin/bash
#SBATCH --job-name=phate_replot
#SBATCH --array=0-{len(datasets)-1}%50
#SBATCH --mem=16G
#SBATCH --cpus-per-task=2
#SBATCH --time=30
#SBATCH --partition=day
#SBATCH --output=logs/phate_replot_%a.out
#SBATCH --error=logs/phate_replot_%a.err

source /home/btd8/manylatents/.venv/bin/activate

DATASETS=({" ".join([d['name'] for d in datasets])})
DATASET_NAME=${{DATASETS[$SLURM_ARRAY_TASK_ID]}}

python scripts/phate/regenerate_phate_plots.py --run --dataset "$DATASET_NAME"
"""
        script_path = Path("slurm_jobs/regenerate_phate_plots.slurm")
        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w") as f:
            f.write(script)
        print(f"Generated SLURM script: {script_path}")
        print(f"To submit: sbatch {script_path}")
        return

    if args.run:
        if args.dataset:
            datasets = [d for d in datasets if d["name"] == args.dataset]
            if not datasets:
                logger.error(f"Dataset not found: {args.dataset}")
                return

        results = []
        for ds in datasets:
            result = process_single_dataset(ds)
            results.append(result)

        success = sum(1 for r in results if r["status"] == "success")
        print(f"\nCompleted: {success}/{len(results)} datasets")


if __name__ == "__main__":
    main()
