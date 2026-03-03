#!/usr/bin/env python3
"""
Main CLI for running PHATE experiments via ManyLatents.

This script provides a unified interface for:
1. Previewing experiments (detecting label keys)
2. Generating ManyLatents configs
3. Running locally for testing
4. Submitting to SLURM via Hydra Submitit

Usage:
    # Preview mode (detect label keys, show what will be generated)
    python scripts/phate/run_phate.py configs/phate_experiments.yaml --preview

    # Generate ManyLatents configs only
    python scripts/phate/run_phate.py configs/phate_experiments.yaml --generate-configs

    # Submit to SLURM via Hydra Submitit
    python scripts/phate/run_phate.py configs/phate_experiments.yaml --submit

    # Run locally for testing (single experiment)
    python scripts/phate/run_phate.py configs/phate_experiments.yaml --local --experiment my_dataset
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.phate.extract_metadata import extract_and_save
from scripts.phate.generate_manylatents_configs import (
    generate_all_configs,
    get_hydra_submit_command,
    get_label_key,
    get_phate_params,
    load_user_config,
)
from scripts.phate.label_detector import batch_detect_labels, preview_labels

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def print_separator(title: str = "") -> None:
    """Print a visual separator."""
    if title:
        title = f" {title} "
    width = 80
    padding = (width - len(title)) // 2
    print("=" * padding + title + "=" * (width - padding - len(title)))


def preview_experiments(
    config: dict[str, Any],
    config_path: Path,
) -> dict[str, Any]:
    """
    Preview experiments: detect label keys, show dataset info.

    Args:
        config: Loaded user config.
        config_path: Path to config file (for resolving relative paths).

    Returns:
        Preview results dict.
    """
    base_dir = Path(config.get("h5ad_base_dir", ""))

    if not base_dir.exists():
        print(f"Warning: h5ad_base_dir does not exist: {base_dir}")

    results = {
        "base_dir": str(base_dir),
        "cluster": config.get("cluster", "yale"),
        "experiments": [],
    }

    for exp in config.get("experiments", []):
        name = exp["name"]
        h5ad_file = exp.get("h5ad_file", name + ".h5ad")

        # Handle relative/absolute paths
        if Path(h5ad_file).is_absolute():
            h5ad_path = Path(h5ad_file)
        else:
            h5ad_path = base_dir / h5ad_file

        print_separator(f"Experiment: {name}")
        print(f"H5AD: {h5ad_path}")

        exp_result = {
            "name": name,
            "h5ad_path": str(h5ad_path),
            "exists": h5ad_path.exists(),
        }

        if not h5ad_path.exists():
            print(f"  ERROR: File not found")
            exp_result["error"] = "File not found"
            results["experiments"].append(exp_result)
            continue

        # Detect label key
        label_key = get_label_key(config, exp)
        print(f"  Label key: {label_key}")

        try:
            preview = preview_labels(h5ad_path, label_key=None if label_key == "auto" else label_key)

            if "detected_key" in preview:
                detected = preview["detected_key"]
                if detected:
                    print(f"  Detected label key: {detected}")
                    print(f"  Categories: {preview.get('n_categories', 'N/A')}")
                    print(f"  Top categories:")
                    for cat in preview.get("categories_preview", [])[:5]:
                        print(f"    - {cat['name']}: {cat['count']} cells")
                else:
                    print(f"  WARNING: No suitable label key detected")
                    print(f"  Available keys: {preview.get('available_keys', [])[:10]}")

                exp_result["label_detection"] = {
                    "detected_key": detected,
                    "n_categories": preview.get("n_categories"),
                    "available_keys": preview.get("available_keys", []),
                }
            elif "error" in preview:
                print(f"  ERROR: {preview['error']}")
                exp_result["error"] = preview["error"]

        except Exception as e:
            print(f"  ERROR: Failed to preview: {e}")
            exp_result["error"] = str(e)

        # Show PHATE params
        phate_params = get_phate_params(config, exp)
        print(f"  PHATE params: knn={phate_params.get('knn')}, t={phate_params.get('t')}, "
              f"decay={phate_params.get('decay')}")
        exp_result["phate_params"] = phate_params

        results["experiments"].append(exp_result)
        print()

    return results


def run_local(
    config: dict[str, Any],
    experiment_name: str,
) -> int:
    """
    Run a single experiment locally (for testing).

    Args:
        config: Loaded user config.
        experiment_name: Name of the experiment to run.

    Returns:
        Exit code.
    """
    # Find the experiment
    exp = next(
        (e for e in config.get("experiments", []) if e["name"] == experiment_name),
        None,
    )

    if not exp:
        logger.error(f"Experiment not found: {experiment_name}")
        return 1

    # Get paths
    base_dir = Path(config.get("h5ad_base_dir", ""))
    h5ad_file = exp.get("h5ad_file", experiment_name + ".h5ad")

    if Path(h5ad_file).is_absolute():
        h5ad_path = Path(h5ad_file)
    else:
        h5ad_path = base_dir / h5ad_file

    if not h5ad_path.exists():
        logger.error(f"H5AD file not found: {h5ad_path}")
        return 1

    import scanpy as sc
    from scvelo.tools import phate as scv_phate

    # Load data
    logger.info(f"Loading data from {h5ad_path}")
    adata = sc.read_h5ad(h5ad_path)

    # Detect label key
    label_key = get_label_key(config, exp)
    if label_key == "auto":
        from scripts.phate.label_detector import detect_label_key

        detected = detect_label_key(adata)
        if not detected:
            logger.warning("No suitable label key detected")
        label_key = detected

    # Get PHATE params
    phate_params = get_phate_params(config, exp)

    logger.info(f"Running PHATE with params: {phate_params}")
    logger.info(f"Data: {adata.n_obs} cells x {adata.n_vars} genes")

    # Run PHATE
    import phate

    phate_op = phate.PHATE(
        n_components=phate_params.get("n_components", 2),
        knn=phate_params.get("knn", 100),
        t=phate_params.get("t", 12),
        decay=phate_params.get("decay", 60),
        random_state=phate_params.get("seed", 42),
    )

    adata.obsm["X_phate"] = phate_op.fit_transform(adata.X)
    logger.info("PHATE embedding complete")

    # Extract metadata
    output_dir = Path(config.get("output_dir", ".")) / experiment_name
    extract_and_save(adata, output_dir, label_key)

    # Save embedding
    if config.get("defaults", {}).get("output", {}).get("save_embedding", True):
        import pandas as pd

        embedding_df = pd.DataFrame(
            adata.obsm["X_phate"],
            columns=[f"PHATE_{i}" for i in range(adata.obsm["X_phate"].shape[1])],
            index=adata.obs_names,
        )
        embedding_path = output_dir / "embedding.csv"
        embedding_df.to_csv(embedding_path)
        logger.info(f"Saved embedding to {embedding_path}")

    logger.info(f"Results saved to {output_dir}")
    return 0


def submit_to_slurm(
    config: dict[str, Any],
    dry_run: bool = False,
) -> int:
    """
    Generate ManyLatents configs and submit via Hydra Submitit.

    Args:
        config: Loaded user config.
        dry_run: If True, print command but don't execute.

    Returns:
        Exit code.
    """
    # Generate configs
    print_separator("Generating ManyLatents configs")
    manifest = generate_all_configs(config)

    # Get the submit command
    cmd = get_hydra_submit_command(manifest)

    print(f"\nHydra Submitit command:")
    print(cmd)

    if dry_run:
        print("\n[Dry run] Not executing command")
        return 0

    # Confirm
    print("\n" + "=" * 80)
    confirm = input("Submit to SLURM? (y/N): ")

    if confirm.lower() != "y":
        print("Aborted")
        return 1

    # Execute
    print("\nSubmitting...")
    try:
        result = subprocess.run(cmd, shell=True, check=True)
        print(f"Submitted. Monitor with: squeue -u $USER")
        return result.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"Submission failed: {e}")
        return e.returncode


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run PHATE experiments via ManyLatents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview experiments (detect label keys)
  python scripts/phate/run_phate.py configs/phate_experiments.yaml --preview

  # Generate ManyLatents configs
  python scripts/phate/run_phate.py configs/phate_experiments.yaml --generate-configs

  # Submit to SLURM
  python scripts/phate/run_phate.py configs/phate_experiments.yaml --submit

  # Run locally for testing
  python scripts/phate/run_phate.py configs/phate_experiments.yaml --local --experiment my_dataset
        """,
    )

    parser.add_argument(
        "config",
        type=Path,
        help="Path to phate_experiments.yaml config file",
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--preview",
        action="store_true",
        help="Preview experiments: detect label keys, show dataset info",
    )
    mode_group.add_argument(
        "--generate-configs",
        action="store_true",
        help="Generate ManyLatents config files only",
    )
    mode_group.add_argument(
        "--submit",
        action="store_true",
        help="Generate configs and submit to SLURM via Hydra Submitit",
    )
    mode_group.add_argument(
        "--local",
        action="store_true",
        help="Run a single experiment locally (for testing)",
    )

    parser.add_argument(
        "--experiment",
        type=str,
        help="Experiment name (required with --local)",
    )

    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print commands but don't execute (for --submit)",
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

    config = load_user_config(args.config)

    # Execute requested mode
    if args.preview:
        preview_experiments(config, args.config)
        return 0

    elif args.generate_configs:
        manifest = generate_all_configs(config)
        print(f"\nGenerated {len(manifest['experiments'])} configs")
        print(f"Output directory: {manifest['output_dir']}")
        return 0

    elif args.local:
        if not args.experiment:
            logger.error("--experiment is required with --local")
            return 1
        return run_local(config, args.experiment)

    elif args.submit:
        return submit_to_slurm(config, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
