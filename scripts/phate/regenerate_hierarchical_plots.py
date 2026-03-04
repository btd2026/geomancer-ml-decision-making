#!/usr/bin/env python3
"""
Regenerate PHATE plots for hierarchical runs without legends.

This script finds all embedding.csv files in the hierarchical structure
and regenerates the phate_plot.png without a legend, using colors from
the original h5ad files.

Resource allocation is based on dataset size:
- small (<50K cells): 16GB, 1hr
- medium (50K-200K cells): 64GB, 2hr
- large (200K-500K cells): 128GB, 6hr
- xlarge (>500K cells): 256GB, 25hr (week partition)
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.resource_config import (
    ResourcePreset,
    get_config,
    get_resource_preset,
    generate_sbatch_header,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# WandB setup
_wandb_initialized = False


def init_wandb():
    """Initialize wandb for logging."""
    global _wandb_initialized

    try:
        import wandb

        wandb.init(
            entity="cesar-valdez-mcgill-university",
            project="manylatent-2026-brian",
            name="phate_replot_no_legend",
            job_type="plot_regeneration",
            config={
                "description": "Regenerating PHATE plots without legends",
            },
            reinit=True,
        )
        _wandb_initialized = True
        logger.info("Initialized wandb")
    except Exception as e:
        logger.warning(f"Failed to initialize wandb: {e}")


def log_to_wandb(dataset_name: str, n_cells: int, status: str, output_path: Path = None):
    """Log regeneration progress to wandb."""
    if not _wandb_initialized:
        return

    try:
        import wandb

        log_data = {
            "dataset_name": dataset_name,
            "n_cells": n_cells,
            "status": status,
        }

        if output_path and output_path.exists():
            log_data["plot"] = wandb.Image(str(output_path))

        wandb.log(log_data)
    except Exception as e:
        logger.warning(f"Failed to log to wandb: {e}")


def finish_wandb():
    """Finish wandb run."""
    global _wandb_initialized

    if _wandb_initialized:
        try:
            import wandb
            wandb.finish()
            logger.info("Finished wandb run")
        except Exception as e:
            logger.warning(f"Failed to finish wandb: {e}")
        finally:
            _wandb_initialized = False


def find_hierarchical_runs(results_dir: Path) -> list[dict]:
    """Find all hierarchical runs with embedding.csv files."""
    runs = []

    for dataset_dir in sorted(results_dir.iterdir()):
        if not dataset_dir.is_dir():
            continue
        if dataset_dir.name.startswith('.'):
            continue

        runs_dir = dataset_dir / "runs"
        if not runs_dir.exists():
            continue

        # Load dataset metadata for cell count
        dataset_metadata_path = dataset_dir / "metadata.json"
        dataset_n_cells = None
        if dataset_metadata_path.exists():
            with open(dataset_metadata_path) as f:
                dataset_metadata = json.load(f)
                dataset_n_cells = dataset_metadata.get("n_obs")

        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue

            embedding_file = run_dir / "embedding.csv"
            if embedding_file.exists():
                # Load config to get h5ad path
                config_file = run_dir / "config.json"
                config = {}
                if config_file.exists():
                    with open(config_file) as f:
                        config = json.load(f)

                # Get cell count from embedding or dataset metadata
                n_cells = dataset_n_cells
                if n_cells is None:
                    # Count lines in embedding file (minus header)
                    try:
                        with open(embedding_file) as f:
                            n_cells = sum(1 for _ in f) - 1
                    except:
                        n_cells = 0

                runs.append({
                    "name": f"{dataset_dir.name}__{run_dir.name}",
                    "dataset_name": dataset_dir.name,
                    "run_dir": run_dir,
                    "embedding_file": embedding_file,
                    "colors_file": run_dir / "colors.json",
                    "h5ad_path": config.get("h5ad_path", ""),
                    "label_key": config.get("label_key", "auto"),
                    "n_cells": n_cells,
                })

    return runs


def load_embeddings(embedding_path: Path) -> tuple[np.ndarray, pd.Index]:
    """Load embeddings from CSV. Returns (embeddings, cell_ids)."""
    df = pd.read_csv(embedding_path, index_col=0)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    return df[numeric_cols].values.astype(np.float64), df.index


def load_colors(colors_path: Path) -> tuple[dict, str]:
    """Load colors from JSON. Returns (colors_dict, label_key)."""
    if colors_path.exists():
        with open(colors_path) as f:
            data = json.load(f)
        return data.get("colors", {}), data.get("label_key", "")
    return {}, ""


def load_labels_from_h5ad(h5ad_path: str, label_key: str, cell_ids: pd.Index) -> np.ndarray:
    """Load labels from h5ad file, aligned with cell_ids.

    NOTE: This can be memory-intensive for large datasets.
    Consider saving labels to a separate file during PHATE run.

    Labels are converted to strings for consistent comparison with colors.json.
    """
    if not h5ad_path:
        return None

    try:
        import scanpy as sc
        # Only load obs (metadata), not X (expression matrix)
        # This is more memory-efficient
        adata = sc.read_h5ad(h5ad_path, backed='r')

        if label_key not in adata.obs.columns:
            logger.warning(f"Label key '{label_key}' not found in h5ad")
            return None

        # Get labels for matching cells
        labels_series = adata.obs[label_key]
        # Convert to string for consistent comparison with colors.json keys
        labels = labels_series.astype(str).reindex(cell_ids).values
        return labels
    except Exception as e:
        logger.warning(f"Could not load labels from h5ad: {e}")
        return None


def load_labels_from_file(run_dir: Path, cell_ids: pd.Index) -> np.ndarray | None:
    """Load labels from a saved labels file (more memory-efficient than h5ad)."""
    labels_file = run_dir / "labels.csv"
    if labels_file.exists():
        try:
            labels_df = pd.read_csv(labels_file, index_col=0)
            if len(labels_df.columns) == 1:
                # Single column - labels
                labels = labels_df.iloc[:, 0].reindex(cell_ids).values
                return labels
        except Exception as e:
            logger.warning(f"Could not load labels from file: {e}")
    return None


def regenerate_plot(
    embedding: np.ndarray,
    labels: np.ndarray,
    colors: dict,
    output_path: Path,
    title: str = "PHATE",
) -> None:
    """Regenerate PHATE plot without legend."""
    fig, ax = plt.subplots(figsize=(10, 8))

    if labels is not None and colors:
        # Plot each label with its color
        unique_labels = sorted(set(str(l) for l in labels if pd.notna(l)))
        for label in unique_labels:
            mask = np.array([str(l) == label if pd.notna(l) else False for l in labels])
            if not mask.any():
                continue
            color = colors.get(label, colors.get(str(label), '#808080'))
            ax.scatter(
                embedding[mask, 0],
                embedding[mask, 1],
                c=color,
                label=str(label),
                alpha=0.6,
                s=10 if len(embedding) > 10000 else 20,
                edgecolors='none',
            )
    else:
        # Simple scatter without labels
        ax.scatter(
            embedding[:, 0],
            embedding[:, 1],
            c='#1f77b4',
            alpha=0.6,
            s=10 if len(embedding) > 10000 else 20,
            edgecolors='none',
        )

    ax.set_xlabel('PHATE 1')
    ax.set_ylabel('PHATE 2')
    ax.set_title(title)
    # NO LEGEND!

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {output_path}")


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

    runs = find_hierarchical_runs(args.results_dir)
    print(f"Found {len(runs)} hierarchical runs")

    if args.preview:
        for i, run in enumerate(runs[:10]):
            n_cells = run.get('n_cells', 0)
            preset = get_resource_preset(n_cells) if n_cells else ResourcePreset.SMALL
            print(f"  {i+1}. {run['name']}")
            print(f"       cells: {n_cells:,}, preset: {preset.value}")
            print(f"       h5ad: {run['h5ad_path'][:60]}..." if run['h5ad_path'] else "       h5ad: N/A")
        if len(runs) > 10:
            print(f"  ... and {len(runs) - 10} more")
        return

    if args.generate_slurm:
        # Group runs by resource preset
        by_preset: dict[ResourcePreset, list[dict]] = {}
        for run in runs:
            n_cells = run.get('n_cells', 0) or 0
            preset = get_resource_preset(n_cells)
            if preset not in by_preset:
                by_preset[preset] = []
            by_preset[preset].append(run)

        # Generate scripts for each preset
        script_paths = []
        for preset, preset_runs in by_preset.items():
            config = get_config(preset)

            # Escape dataset names for bash array
            dataset_names = [r['name'].replace(" ", "\\ ") for r in preset_runs]
            datasets_str = " ".join(dataset_names)

            script = f"""#!/bin/bash
#SBATCH --job-name=phate_replot_{preset.value}
#SBATCH --array=0-{len(preset_runs)-1}%{config.max_concurrent}
#SBATCH --mem={config.mem_gb}G
#SBATCH --cpus-per-task={config.cpus}
#SBATCH --time={config.time_hours:02d}:00:00
#SBATCH --partition={config.partition}
#SBATCH --output=logs/phate_replot_{preset.value}_%a.out
#SBATCH --error=logs/phate_replot_{preset.value}_%a.err

# Auto-generated by regenerate_hierarchical_plots.py
# Preset: {preset.value} for {len(preset_runs)} datasets
# Size threshold: {preset.name} (memory: {config.mem_gb}GB, time: {config.time_hours}hr)

source /home/btd8/manylatents/.venv/bin/activate

DATASETS=({datasets_str})
DATASET_NAME=${{DATASETS[$SLURM_ARRAY_TASK_ID]}}

python scripts/phate/regenerate_hierarchical_plots.py --run --dataset "$DATASET_NAME"
"""
            script_path = Path(f"slurm_jobs/regenerate_plots_{preset.value}.slurm")
            script_path.parent.mkdir(parents=True, exist_ok=True)
            with open(script_path, "w") as f:
                f.write(script)
            script_paths.append((preset, len(preset_runs), script_path))

        print("Generated SLURM scripts by resource preset:")
        print("-" * 60)
        for preset, n_jobs, script_path in sorted(script_paths, key=lambda x: x[1], reverse=True):
            config = get_config(preset)
            print(f"  {preset.value:8s}: {n_jobs:3d} jobs, {config.mem_gb}GB, {config.time_hours}hr, {config.partition}")
            print(f"           -> {script_path}")
        print()
        print("To submit all:")
        for _, _, script_path in script_paths:
            print(f"  sbatch {script_path}")
        return

    if args.run:
        # Initialize wandb
        init_wandb()

        if args.dataset:
            runs = [r for r in runs if args.dataset in r['name']]
            if not runs:
                logger.error(f"Dataset not found: {args.dataset}")
                finish_wandb()
                return

        success = 0
        for i, run in enumerate(runs):
            logger.info(f"[{i+1}/{len(runs)}] {run['name']}")

            try:
                embedding, cell_ids = load_embeddings(run['embedding_file'])
                colors, label_key = load_colors(run['colors_file'])

                # Use label_key from colors.json if available, else from config
                if not label_key:
                    label_key = run['label_key']

                # Load labels - prefer labels.csv file (memory-efficient)
                # Fall back to h5ad only if labels.csv doesn't exist
                labels = load_labels_from_file(run['run_dir'], cell_ids)
                if labels is None and run['h5ad_path'] and label_key:
                    logger.info("  Loading labels from h5ad (slower, more memory)...")
                    labels = load_labels_from_h5ad(run['h5ad_path'], label_key, cell_ids)

                # Remove old plot
                old_plot = run['run_dir'] / "phate_plot.png"
                if old_plot.exists():
                    old_plot.unlink()

                regenerate_plot(embedding, labels, colors, old_plot, run['dataset_name'])

                # Log to wandb
                log_to_wandb(run['name'], len(embedding), "success", old_plot)

                success += 1
            except Exception as e:
                logger.error(f"  Failed: {e}")
                log_to_wandb(run['name'], 0, f"failed: {e}")

        print(f"\nCompleted: {success}/{len(runs)} runs")

        # Finish wandb
        finish_wandb()


if __name__ == "__main__":
    main()
