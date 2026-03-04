#!/usr/bin/env python3
"""
Main CLI for computing DSE metrics on existing PHATE embeddings.

This script provides a unified interface for:
1. Previewing embeddings (discovering available embedding files)
2. Computing DSE metrics on embeddings
3. Submitting to SLURM for batch processing

Usage:
    # Preview mode (discover available embeddings)
    python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --preview

    # Generate SLURM job script
    python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --generate-slurm

    # Submit to SLURM
    python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --submit

    # Run locally for testing
    python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --local --dataset <dataset_id>

    # Run all locally
    python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --local
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml

# Setup logging
logger = logging.getLogger(__name__)

# wandb setup
_wandb_initialized = False
_wandb_run = None


def init_wandb(config: dict[str, Any]) -> bool:
    """Initialize wandb if configured."""
    global _wandb_initialized, _wandb_run

    wandb_config = config.get("wandb")
    if not wandb_config:
        return False

    try:
        import wandb

        entity = wandb_config.get("entity")
        project = wandb_config.get("project")

        if not entity or not project:
            logger.warning("WandB entity or project not specified, skipping wandb logging")
            return False

        _wandb_run = wandb.init(
            entity=entity,
            project=project,
            name="dse_metrics_on_phate",
            job_type="dse_metrics",
            config={
                "dse_params": config.get("defaults", {}).get("dse", {}),
                "embeddings_dir": str(config.get("embeddings_dir", "")),
            },
            reinit=True,
        )
        _wandb_initialized = True
        logger.info(f"Initialized wandb: {entity}/{project}")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize wandb: {e}")
        return False


def log_to_wandb(
    dataset_name: str,
    metrics: dict[str, Any],
    embedding_file: str,
    n_samples: int,
    n_features: int,
) -> None:
    """Log DSE metrics to wandb for a single dataset."""
    global _wandb_initialized, _wandb_run

    if not _wandb_initialized or _wandb_run is None:
        return

    try:
        import wandb

        # Create a wandb table row for this dataset
        log_data = {
            "dataset_name": dataset_name,
            "embedding_file": embedding_file,
            "n_samples": n_samples,
            "n_features": n_features,
            **{k: v for k, v in metrics.items() if isinstance(v, (int, float, str))},
        }

        wandb.log(log_data)
        logger.info(f"  Logged to wandb: {dataset_name}")
    except Exception as e:
        logger.warning(f"Failed to log to wandb: {e}")


def finish_wandb() -> None:
    """Finish wandb run."""
    global _wandb_initialized, _wandb_run

    if _wandb_initialized and _wandb_run is not None:
        try:
            import wandb
            wandb.finish()
            logger.info("Finished wandb run")
        except Exception as e:
            logger.warning(f"Failed to finish wandb: {e}")
        finally:
            _wandb_initialized = False
            _wandb_run = None


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def load_config(config_path: Path) -> dict[str, Any]:
    """Load the YAML config file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_dse_params(config: dict[str, Any]) -> dict[str, Any]:
    """Get DSE parameters from config defaults."""
    return config.get("defaults", {}).get("dse", {})


def get_slurm_resources(config: dict[str, Any]) -> dict[str, Any]:
    """Get SLURM resources from preset."""
    preset_name = config.get("defaults", {}).get("slurm_preset", "small")
    presets = config.get("slurm_presets", {})
    return presets.get(preset_name, presets.get("small", {}))


def discover_embeddings(embeddings_dir: Path) -> list[dict[str, Any]]:
    """
    Discover all embedding files in the embeddings directory.

    Only uses hierarchical structure (dataset/runs/run_id/embedding.csv).
    Skips UUID directories (flat structure).

    Returns list of dicts with:
        - name: dataset/run identifier
        - embedding_dir: path to the directory containing embeddings
        - embedding_file: path to the embedding CSV file
    """
    embeddings_dir = Path(embeddings_dir)
    if not embeddings_dir.exists():
        logger.error(f"Embeddings directory does not exist: {embeddings_dir}")
        return []

    results = []
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE
    )

    for item in sorted(embeddings_dir.iterdir()):
        if not item.is_dir():
            continue

        # Skip hidden directories
        if item.name.startswith('.'):
            continue

        # Skip UUID directories (flat structure)
        if uuid_pattern.match(item.name):
            continue

        # Check for hierarchical structure (dataset/runs/run_id/)
        runs_dir = item / "runs"
        if runs_dir.exists() and runs_dir.is_dir():
            # Hierarchical structure
            for run_dir in sorted(runs_dir.iterdir()):
                if not run_dir.is_dir():
                    continue

                # Look for embedding.csv
                embedding_file = run_dir / "embedding.csv"
                if embedding_file.exists():
                    results.append({
                        "name": f"{item.name}__{run_dir.name}",
                        "embedding_dir": str(run_dir),
                        "embedding_file": str(embedding_file),
                    })

    return results


def load_embeddings(embedding_path: Path) -> Optional[np.ndarray]:
    """Load embeddings from CSV file."""
    try:
        df = pd.read_csv(embedding_path, index_col=0)
        # Select only numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            # Try without index column
            df = pd.read_csv(embedding_path)
            numeric_cols = df.select_dtypes(include=[np.number]).columns
        return df[numeric_cols].values.astype(np.float64)
    except Exception as e:
        logger.error(f"Failed to load embeddings from {embedding_path}: {e}")
        return None


def compute_dse_metrics(
    embeddings: np.ndarray,
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute DSE metrics on embeddings using ManyLatents.

    Args:
        embeddings: numpy array of shape (n_samples, n_features)
        params: DSE parameters from config

    Returns:
        Dictionary of metric results
    """
    # Import ManyLatents DSE metric
    sys.path.insert(0, "/home/btd8/manylatents")
    from manylatents.metrics.diffusion_spectral_entropy import DiffusionSpectralEntropy

    # Extract parameters
    output_mode = params.get("output_mode", "eigenvalue_count")
    t_high = params.get("t_high", [10, 50, 100, 200, 500])
    numerical_floor = params.get("numerical_floor", 1e-6)
    kernel = params.get("kernel", "knn")
    k = params.get("k", 15)
    alpha = params.get("alpha", 1.0)
    max_N = params.get("max_N", 10000)
    random_seed = params.get("random_seed", 42)

    results = {}

    # Handle t_high as list or single value
    if isinstance(t_high, list):
        for t in t_high:
            result = DiffusionSpectralEntropy(
                embeddings=embeddings,
                output_mode=output_mode,
                t_high=t,
                numerical_floor=numerical_floor,
                kernel=kernel,
                k=k,
                alpha=alpha,
                max_N=max_N,
                random_seed=random_seed,
            )
            results[f"dse_count_t{t}"] = float(result) if not isinstance(result, dict) else result
    else:
        result = DiffusionSpectralEntropy(
            embeddings=embeddings,
            output_mode=output_mode,
            t_high=t_high,
            numerical_floor=numerical_floor,
            kernel=kernel,
            k=k,
            alpha=alpha,
            max_N=max_N,
            random_seed=random_seed,
        )
        results["dse_count"] = float(result) if not isinstance(result, dict) else result

    # Also compute entropy mode
    entropy_result = DiffusionSpectralEntropy(
        embeddings=embeddings,
        output_mode="entropy",
        t=params.get("t", 3),
        kernel=kernel,
        k=k,
        alpha=alpha,
        max_N=max_N,
        random_seed=random_seed,
    )
    results["dse_entropy"] = float(entropy_result)

    return results


def process_single_dataset(
    dataset_info: dict[str, Any],
    config: dict[str, Any],
    output_dir: Path,
    save_to_source_dir: bool = True,
) -> dict[str, Any]:
    """
    Process a single dataset: load embeddings, compute DSE metrics, save results.

    Args:
        dataset_info: Dict with name, embedding_dir, embedding_file
        config: Full config dict
        output_dir: Base output directory
        save_to_source_dir: If True, also save metrics to the source embedding directory

    Returns:
        Results dict
    """
    name = dataset_info["name"]
    embedding_path = Path(dataset_info["embedding_file"])
    embedding_dir = Path(dataset_info["embedding_dir"])

    logger.info(f"Processing: {name}")
    logger.info(f"  Embedding file: {embedding_path}")

    # Load embeddings
    embeddings = load_embeddings(embedding_path)
    if embeddings is None:
        return {"name": name, "status": "error", "error": "Failed to load embeddings"}

    n_samples, n_features = embeddings.shape
    logger.info(f"  Shape: {n_samples} samples x {n_features} dimensions")

    # Get DSE parameters
    dse_params = get_dse_params(config)

    # Compute DSE metrics
    logger.info(f"  Computing DSE metrics...")
    try:
        metrics = compute_dse_metrics(embeddings, dse_params)
    except Exception as e:
        logger.error(f"  Error computing metrics: {e}")
        return {"name": name, "status": "error", "error": str(e)}

    # Prepare output
    result = {
        "name": name,
        "status": "success",
        "embedding_file": str(embedding_path),
        "n_samples": n_samples,
        "n_features": n_features,
        "algorithm_type": "dse",  # Mark as DSE metrics
        "dse_params": {
            "kernel": dse_params.get("kernel", "knn"),
            "k": dse_params.get("k", 15),
            "alpha": dse_params.get("alpha", 1.0),
        },
        **metrics,
    }

    # Save to output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{name}_dse_metrics.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"  Saved: {result_path}")

    # Also save to source embedding directory (for gallery integration)
    if save_to_source_dir:
        source_result_path = embedding_dir / "dse_metrics.json"
        with open(source_result_path, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"  Saved to source dir: {source_result_path}")

    # Log to wandb
    log_to_wandb(
        dataset_name=name,
        metrics=metrics,
        embedding_file=str(embedding_path),
        n_samples=n_samples,
        n_features=n_features,
    )

    return result


def preview_embeddings(config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Preview available embeddings.

    Returns list of discovered embedding datasets.
    """
    embeddings_dir = Path(config.get("embeddings_dir", ""))
    print(f"\nEmbeddings directory: {embeddings_dir}")

    datasets = discover_embeddings(embeddings_dir)
    print(f"\nDiscovered {len(datasets)} embedding datasets:\n")

    for i, ds in enumerate(datasets[:10]):  # Show first 10
        print(f"  {i+1}. {ds['name']}")
        print(f"     File: {Path(ds['embedding_file']).name}")

    if len(datasets) > 10:
        print(f"  ... and {len(datasets) - 10} more")

    # Show DSE params
    dse_params = get_dse_params(config)
    print(f"\nDSE parameters:")
    print(f"  output_mode: {dse_params.get('output_mode')}")
    print(f"  t_high: {dse_params.get('t_high')}")
    print(f"  kernel: {dse_params.get('kernel')}")
    print(f"  k: {dse_params.get('k')}")
    print(f"  alpha: {dse_params.get('alpha')}")

    return datasets


def run_local(
    config: dict[str, Any],
    dataset_name: Optional[str] = None,
) -> int:
    """
    Run DSE metrics locally.

    Args:
        config: Loaded config
        dataset_name: Specific dataset to process (None for all)

    Returns:
        Exit code
    """
    embeddings_dir = Path(config.get("embeddings_dir", ""))
    output_dir = Path(config.get("output_dir", ""))

    # Initialize wandb
    init_wandb(config)

    # Discover datasets
    datasets = discover_embeddings(embeddings_dir)
    if not datasets:
        logger.error("No embedding datasets found")
        finish_wandb()
        return 1

    # Filter to specific dataset if requested
    if dataset_name:
        datasets = [d for d in datasets if d["name"] == dataset_name]
        if not datasets:
            logger.error(f"Dataset not found: {dataset_name}")
            finish_wandb()
            return 1

    logger.info(f"Processing {len(datasets)} datasets")

    results = []
    for i, ds in enumerate(datasets):
        logger.info(f"\n[{i+1}/{len(datasets)}] {ds['name']}")
        result = process_single_dataset(ds, config, output_dir)
        results.append(result)

        if result["status"] == "success":
            # Print metrics
            for key, value in result.items():
                if key.startswith("dse_"):
                    print(f"  {key}: {value}")

    # Save combined results
    combined_path = output_dir / "all_dse_metrics.json"
    with open(combined_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nSaved combined results to {combined_path}")

    # Summary
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"\nCompleted: {success_count}/{len(results)} datasets")

    # Log summary table to wandb
    if _wandb_initialized:
        try:
            import wandb
            # Create a summary table
            table = wandb.Table(
                columns=["dataset_name", "n_samples", "dse_count_t10", "dse_count_t50", "dse_count_t100", "dse_count_t200", "dse_count_t500", "dse_entropy"],
                data=[
                    [r["name"], r.get("n_samples"), r.get("dse_count_t10"), r.get("dse_count_t50"),
                     r.get("dse_count_t100"), r.get("dse_count_t200"), r.get("dse_count_t500"), r.get("dse_entropy")]
                    for r in results if r["status"] == "success"
                ]
            )
            wandb.log({"dse_metrics_summary": table})
            logger.info("Logged summary table to wandb")
        except Exception as e:
            logger.warning(f"Failed to log summary table: {e}")

    # Finish wandb
    finish_wandb()

    return 0


def generate_slurm_script(
    config: dict[str, Any],
    output_path: Optional[Path] = None,
) -> str:
    """
    Generate SLURM job script for batch processing.

    Args:
        config: Loaded config
        output_path: Path to write script (optional)

    Returns:
        SLURM script content
    """
    embeddings_dir = Path(config.get("embeddings_dir", ""))
    datasets = discover_embeddings(embeddings_dir)
    resources = get_slurm_resources(config)

    if output_path is None:
        output_path = Path("slurm_jobs/run_dse_metrics_array.slurm")

    # Create SLURM script
    script = f"""#!/bin/bash
#SBATCH --job-name=dse_metrics
#SBATCH --array=0-{len(datasets)-1}%50
#SBATCH --mem={resources.get('mem_gb', 32)}G
#SBATCH --cpus-per-task={resources.get('cpus_per_task', 4)}
#SBATCH --time={resources.get('timeout_min', 60)}
#SBATCH --partition={resources.get('partition', 'day')}
#SBATCH --output=logs/dse_metrics_%a.out
#SBATCH --error=logs/dse_metrics_%a.err

# Load conda environment
source ~/.bashrc
conda activate geomancer

# Set paths
CONFIG_FILE="{Path.cwd()}/configs/dse_metrics_experiments.yaml"
OUTPUT_DIR="{config.get('output_dir', '')}"

# Dataset list
DATASETS=({" ".join([d['name'] for d in datasets])})

# Get dataset for this array task
DATASET_NAME=${{DATASETS[$SLURM_ARRAY_TASK_ID]}}

echo "Processing dataset: $DATASET_NAME"
echo "SLURM_ARRAY_TASK_ID: $SLURM_ARRAY_TASK_ID"

# Run DSE metrics
python scripts/dse/run_dse_metrics.py "$CONFIG_FILE" \\
    --local \\
    --dataset "$DATASET_NAME"

echo "Done: $DATASET_NAME"
"""

    # Write script
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(script)

    print(f"Generated SLURM script: {output_path}")
    print(f"  Jobs: {len(datasets)}")
    print(f"  Resources: {resources.get('cpus_per_task', 4)} CPUs, {resources.get('mem_gb', 32)}G, {resources.get('timeout_min', 60)} min")
    print(f"\nTo submit: sbatch {output_path}")

    return script


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute DSE metrics on existing PHATE embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview available embeddings
  python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --preview

  # Generate SLURM job script
  python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --generate-slurm

  # Run locally on all embeddings
  python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --local

  # Run locally on specific dataset
  python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --local --dataset <dataset_id>
        """,
    )

    parser.add_argument(
        "config",
        type=Path,
        help="Path to dse_metrics_experiments.yaml config file",
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--preview",
        action="store_true",
        help="Preview available embeddings",
    )
    mode_group.add_argument(
        "--generate-slurm",
        action="store_true",
        help="Generate SLURM job script",
    )
    mode_group.add_argument(
        "--local",
        action="store_true",
        help="Run locally (optionally with --dataset for single dataset)",
    )

    parser.add_argument(
        "--dataset",
        type=str,
        help="Process specific dataset only (for --local mode)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Load config
    if not args.config.exists():
        logger.error(f"Config file not found: {args.config}")
        return 1

    config = load_config(args.config)

    # Execute requested mode
    if args.preview:
        preview_embeddings(config)
        return 0

    elif args.generate_slurm:
        generate_slurm_script(config)
        return 0

    elif args.local:
        return run_local(config, args.dataset)

    return 0


if __name__ == "__main__":
    sys.exit(main())
