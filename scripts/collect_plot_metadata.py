#!/usr/bin/env python3
"""
Collect plot metadata from completed ManyLatents experiment outputs.

This script reads plot_metadata.json files created during SLURM job execution
and consolidates them into a single label_categories.json file mapped by WandB run ID.
"""

import json
import sys
from pathlib import Path

def load_wandb_metadata(wandb_metadata_path: Path) -> dict:
    """Load wandb metadata and create experiment name to run ID mapping."""
    with open(wandb_metadata_path, 'r') as f:
        wandb_data = json.load(f)

    # Create mapping: experiment_name -> run_id
    exp_to_run_id = {}
    for run_id, run_info in wandb_data.items():
        exp_name = run_info.get('name', '')
        if exp_name:
            exp_to_run_id[exp_name] = run_id

    return wandb_data, exp_to_run_id


def collect_metadata(
    manylatents_output_dir: Path,
    exp_to_run_id: dict,
    wandb_data: dict,
) -> dict:
    """Collect metadata from all experiment outputs."""
    results = {}
    missing = []

    for exp_dir in sorted(manylatents_output_dir.iterdir()):
        if not exp_dir.is_dir():
            continue

        metadata_path = exp_dir / "plot_metadata.json"
        if not metadata_path.exists():
            # Try to find using run_id directly
            run_id = exp_dir.name
            if run_id in exp_to_run_id:
                # Check for this run ID in a different naming scheme
                pass
            missing.append(exp_dir.name)
            continue

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Map to run ID using experiment name
            exp_name = exp_dir.name
            if exp_name in exp_to_run_id:
                run_id = exp_to_run_id[exp_name]
                results[run_id] = {
                    "label_key": metadata["label_key"],
                    "categories": metadata["categories"],
                    "num_categories": metadata["num_categories"],
                    "dataset_name": wandb_data[run_id].get("dataset_name", "Unknown"),
                    "source": "manylatents_output",
                    "n_cells": metadata.get("n_cells", 0),
                    "n_genes": metadata.get("n_genes", 0),
                    "adata_file": metadata.get("adata_file", ""),
                }
                print(f"{run_id}: {metadata['label_key']} -> {metadata['num_categories']} categories")
        except Exception as e:
            print(f"Warning: Could not process {exp_dir}: {e}")

    return results, missing


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect plot metadata from ManyLatents outputs"
    )
    parser.add_argument(
        "--manylatents-output",
        default="/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs",
        help="Directory containing ManyLatents experiment outputs"
    )
    parser.add_argument(
        "--wandb-metadata",
        default="wandb_gallery_replit/wandb_metadata.json",
        help="Path to wandb_metadata.json"
    )
    parser.add_argument(
        "--output",
        default="wandb_gallery_replit/label_categories.json",
        help="Output path for label_categories.json"
    )

    args = parser.parse_args()

    print("Loading WandB metadata...")
    wandb_data, exp_to_run_id = load_wandb_metadata(Path(args.wandb_metadata))
    print(f"  Loaded {len(wandb_data)} runs")
    print(f"  Found {len(exp_to_run_id)} experiment names")

    print(f"\nScanning {args.manylatents_output} for plot_metadata.json files...")
    results, missing = collect_metadata(Path(args.manylatents_output), exp_to_run_id, wandb_data)

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Collected metadata: {len(results)} runs")
    print(f"Missing metadata: {len(missing)} experiment directories")
    print(f"Saved to: {output_path}")

    if missing:
        print(f"\nMissing (no plot_metadata.json):")
        for name in missing[:10]:
            print(f"  - {name}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")


if __name__ == "__main__":
    main()
