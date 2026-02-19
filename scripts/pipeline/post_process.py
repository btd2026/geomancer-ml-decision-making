#!/usr/bin/env python3
"""
Post-processing utilities for ManyLatents experiment outputs.

This module provides functions for extracting metadata from completed experiments,
such as plot categories, colors, and label information from h5ad files.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

try:
    import anndata as ad
except ImportError:
    ad = None


def extract_plot_metadata_from_h5ad(
    hdata_path: str,
    label_key: str,
    max_categories: int = 100,
) -> Dict[str, Any]:
    """
    Extract plot metadata from an h5ad file.

    This includes:
    - Label key used for coloring
    - Unique category values
    - Number of categories
    - Category counts

    Args:
        adata_path: Path to h5ad file
        label_key: Column name in obs that was used for coloring
        max_categories: Maximum categories to extract

    Returns:
        Dictionary with plot metadata
    """
    if ad is None:
        raise ImportError("anndata not available. Install with: pip install anndata")

    adata = ad.read_h5ad(adata_path)

    if label_key not in adata.obs:
        raise ValueError(f"Label key '{label_key}' not found in adata.obs")

    # Get categories
    if hasattr(adata.obs[label_key], 'cat'):
        categories = adata.obs[label_key].cat.categories.tolist()
    else:
        categories = adata.obs[label_key].unique().tolist()

    # Convert to strings and filter
    cleaned_categories = []
    for cat in categories:
        cat_str = str(cat)
        if cat_str not in ['nan', 'None', 'NA', '<NA>']:
            cleaned_categories.append(cat_str)

    # Limit categories
    if len(cleaned_categories) > max_categories:
        cleaned_categories = cleaned_categories[:max_categories]

    # Get category counts
    value_counts = adata.obs[label_key].value_counts()
    category_counts = {}
    for cat, count in value_counts.items():
        cat_str = str(cat)
        if cat_str not in ['nan', 'None', 'NA', '<NA>']:
            category_counts[cat_str] = int(count)

    # Get basic stats
    n_cells = len(adata)
    n_genes = adata.n_vars

    metadata = {
        "label_key": label_key,
        "categories": cleaned_categories,
        "num_categories": len(cleaned_categories),
        "category_counts": category_counts,
        "n_cells": n_cells,
        "n_genes": n_genes,
        "adata_file": Path(adata_path).name,
    }

    return metadata


def extract_all_metadata_from_output(
    output_dir: Path,
    metadata_file: str = "plot_metadata.json",
) -> Dict[str, Dict[str, Any]]:
    """
    Extract metadata from all runs in an output directory.

    Args:
        output_dir: Base output directory containing experiment subdirectories
        metadata_file: Name of metadata file within each experiment directory

    Returns:
        Dictionary mapping experiment_name to metadata
    """
    results = {}

    for exp_dir in output_dir.iterdir():
        if not exp_dir.is_dir():
            continue

        metadata_path = exp_dir / metadata_file
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    results[exp_dir.name] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load {metadata_path}: {e}")

    return results


def collect_all_metadata(
    output_base: Path,
    output_file: Path,
    metadata_filename: str = "plot_metadata.json",
) -> None:
    """
    Collect all plot metadata into a single JSON file.

    This creates a consolidated file similar to label_categories.json
    but sourced from the actual experiment outputs.

    Args:
        output_base: Base directory containing experiment outputs
        output_file: Path to output consolidated JSON file
        metadata_filename: Name of metadata file in each experiment directory
    """
    all_metadata = {}

    for exp_dir in output_base.iterdir():
        if not exp_dir.is_dir():
            continue

        metadata_path = exp_dir / metadata_filename
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    # Use experiment directory name as key
                    all_metadata[exp_dir.name] = metadata
            except Exception as e:
                print(f"Warning: Could not load {metadata_path}: {e}")

    # Save consolidated file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(all_metadata, f, indent=2)

    print(f"Collected metadata for {len(all_metadata)} experiments")
    print(f"Saved to: {output_file}")


def regenerate_label_categories_from_outputs(
    manylatents_output_dir: Path,
    wandb_metadata_path: Path,
    output_path: Path,
    max_categories: int = 100,
) -> None:
    """
    Regenerate label_categories.json from ManyLatents experiment outputs.

    This reads the plot_metadata.json files from completed ManyLatents runs
    and creates a label_categories.json file mapped by WandB run ID.

    Args:
        manylatents_output_dir: Directory containing ManyLatents experiment outputs
        wandb_metadata_path: Path to wandb_metadata.json for run ID mapping
        output_path: Path to save label_categories.json
        max_categories: Maximum categories per dataset
    """
    # Load wandb metadata to map experiment names to run IDs
    with open(wandb_metadata_path, 'r') as f:
        wandb_data = json.load(f)

    # Create mapping: experiment_name -> run_id
    exp_to_run_id = {}
    for run_id, run_info in wandb_data.items():
        exp_name = run_info.get('name', '')
        if exp_name:
            exp_to_run_id[exp_name] = run_id

    # Collect metadata from outputs
    results = {}
    for exp_dir in manylatents_output_dir.iterdir():
        if not exp_dir.is_dir():
            continue

        metadata_path = exp_dir / "plot_metadata.json"
        if not metadata_path.exists():
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
                }
                print(f"{run_id}: {metadata['label_key']} -> {metadata['num_categories']} categories")
        except Exception as e:
            print(f"Warning: Could not process {exp_dir}: {e}")

    # Save to label_categories.json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} runs to {output_path}")


def main():
    """CLI for post-processing utilities."""
    import argparse

    parser = argparse.ArgumentParser(description="Post-process ManyLatents outputs")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Extract from single h5ad
    extract_parser = subparsers.add_parser('extract', help='Extract metadata from h5ad file')
    extract_parser.add_argument('--adata', required=True, help='Path to h5ad file')
    extract_parser.add_argument('--label-key', required=True, help='Label key used')
    extract_parser.add_argument('--output', required=True, help='Output JSON file')

    # Collect all metadata
    collect_parser = subparsers.add_parser('collect', help='Collect all metadata from outputs')
    collect_parser.add_argument('--output-dir', required=True, help='Base output directory')
    collect_parser.add_argument('--output', required=True, help='Output JSON file')

    # Regenerate label_categories
    regenerate_parser = subparsers.add_parser('regenerate', help='Regenerate label_categories.json')
    regenerate_parser.add_argument('--manylatents-output', required=True)
    regenerate_parser.add_argument('--wandb-metadata', required=True)
    regenerate_parser.add_argument('--output', required=True)

    args = parser.parse_args()

    if args.command == 'extract':
        metadata = extract_plot_metadata_from_h5ad(args.adata, args.label_key)
        with open(args.output, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        print(f"Extracted metadata with {metadata['num_categories']} categories")
        print(f"Saved to: {args.output}")

    elif args.command == 'collect':
        collect_all_metadata(Path(args.output_dir), Path(args.output))

    elif args.command == 'regenerate':
        regenerate_label_categories_from_outputs(
            manylatents_output_dir=Path(args.manylatents_output),
            wandb_metadata_path=Path(args.wandb_metadata),
            output_path=Path(args.output),
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
