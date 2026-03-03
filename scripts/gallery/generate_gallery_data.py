#!/usr/bin/env python3
"""
Generate gallery data from PHATE results directory.

This script scans the PHATE results directory and generates a unified
gallery_data.json file that can be used by the gallery HTML interface.

Supports both:
1. New hierarchical structure: dataset/runs/run_id/
2. Legacy UUID-based structure (flat directories)

The output format is designed to be algorithm-agnostic, supporting
PHATE, Reeb graph, DSE, and other algorithms in the future.
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(filepath: Path) -> dict | None:
    """Load JSON file if it exists."""
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return None


def scan_hierarchical_dataset(dataset_dir: Path) -> list[dict]:
    """
    Scan a dataset directory with hierarchical structure (dataset/runs/run_id/).

    Returns a list of run data dictionaries.
    """
    runs = []
    runs_dir = dataset_dir / "runs"

    if not runs_dir.exists():
        return runs

    dataset_metadata = load_json(dataset_dir / "metadata.json") or {}

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        run_metadata = load_json(run_dir / "metadata.json") or {}
        colors_data = load_json(run_dir / "colors.json") or {}
        config_data = load_json(run_dir / "config.json") or {}

        # Find PHATE plot image
        image_path = None
        for pattern in ["phate_plot.png", "phate_plot_*.png", "*phate*.png"]:
            matches = list(run_dir.glob(pattern))
            if matches:
                image_path = matches[0]
                break

        # Build colors dict - convert from various formats
        colors = colors_data.get("colors", {})
        if isinstance(colors, list):
            # Convert list to dict if needed (legacy format)
            colors = {f"Category {i+1}": c for i, c in enumerate(colors)}

        # Determine algorithm type
        algorithm_type = run_metadata.get("algorithm_type", "phate")
        if "phate" in run_dir.name.lower() or "phate_params" in run_metadata:
            algorithm_type = "phate"
        elif "reeb" in run_dir.name.lower():
            algorithm_type = "reeb"
        elif "dse" in run_dir.name.lower():
            algorithm_type = "dse"

        run_data = {
            # Gallery run ID (unique identifier)
            "gallery_run_id": f"{dataset_dir.name}__{run_dir.name}",

            # Dataset level info
            "dataset_name": dataset_metadata.get("name", dataset_dir.name),
            "dataset_description": dataset_metadata.get("description", ""),
            "n_obs": dataset_metadata.get("n_obs"),
            "n_vars": dataset_metadata.get("n_vars"),
            "h5ad_path": dataset_metadata.get("h5ad_path", ""),

            # Run level info
            "run_id": run_dir.name,
            "algorithm_type": algorithm_type,
            "label_key": run_metadata.get("label_key", colors_data.get("label_key", "unknown")),
            "n_categories": run_metadata.get("n_categories", colors_data.get("n_categories", 0)),
            "phate_params": run_metadata.get("phate_params", {}),
            "timestamp": run_metadata.get("timestamp", ""),

            # Colors (label_name -> hex_color mapping)
            "colors": colors,
            "categories": list(colors.keys()),

            # Image info
            "image_filename": image_path.name if image_path else None,
            "has_image": image_path is not None,

            # Source paths
            "source_dir": str(run_dir),
        }

        runs.append(run_data)

    return runs


def scan_legacy_uuid_directory(uuid_dir: Path) -> dict | None:
    """
    Scan a legacy UUID-based directory (flat structure from old WandB runs).

    Returns a single run data dictionary or None if not valid.
    """
    # Look for metadata file
    metadata_files = list(uuid_dir.glob("*.json"))
    if not metadata_files:
        return None

    # Try to extract info from filenames
    dataset_name = None
    label_key = None

    for f in uuid_dir.iterdir():
        name = f.name.lower()
        if "phate" in name and f.suffix == ".png":
            # Extract dataset name from filename pattern
            # e.g., embedding_plot_phate_k100_017837df-b8be-4a4f-bc08-c5f14bd8815a.png_20251117_091624.png
            parts = f.stem.split("_")
            for i, part in enumerate(parts):
                if part == "phate" and i > 0:
                    # This might be a label_key
                    pass

    # For legacy directories, we need to get info from the gallery_data.json
    # that was already created from WandB metadata
    return None  # Legacy directories are handled separately


def generate_gallery_data(
    phate_results_dir: Path,
    output_dir: Path,
    legacy_metadata_path: Path | None = None,
    copy_images: bool = False,
    symlink_images: bool = True,
) -> dict:
    """
    Generate gallery data from PHATE results directory.

    Args:
        phate_results_dir: Path to PHATE results directory
        output_dir: Path to output directory for gallery_data.json
        legacy_metadata_path: Path to existing gallery_data.json with WandB metadata
        copy_images: Whether to copy images to output directory
        symlink_images: Whether to create symlinks to images (default)

    Returns:
        Dictionary containing the gallery data
    """
    gallery_data = {
        "generated_at": datetime.now().isoformat(),
        "source_dir": str(phate_results_dir),
        "datasets": {},  # dataset_name -> {metadata, runs: [run_ids]}
        "runs": {},  # gallery_run_id -> run_data
    }

    # Create images directory
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Scan hierarchical datasets (new structure)
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE
    )

    for item in phate_results_dir.iterdir():
        if not item.is_dir():
            continue

        # Skip UUID directories (legacy) and special directories
        if uuid_pattern.match(item.name) or item.name.startswith("_"):
            continue

        # Scan hierarchical dataset
        runs = scan_hierarchical_dataset(item)

        if runs:
            dataset_name = runs[0].get("dataset_name", item.name)
            gallery_data["datasets"][dataset_name] = {
                "name": dataset_name,
                "description": runs[0].get("dataset_description", ""),
                "n_obs": runs[0].get("n_obs"),
                "n_vars": runs[0].get("n_vars"),
                "h5ad_path": runs[0].get("h5ad_path", ""),
                "runs": [],
            }

            for run_data in runs:
                gallery_run_id = run_data["gallery_run_id"]
                gallery_data["datasets"][dataset_name]["runs"].append(gallery_run_id)
                gallery_data["runs"][gallery_run_id] = run_data

                # Handle image file
                if run_data["has_image"] and run_data["image_filename"]:
                    source_image = Path(run_data["source_dir"]) / run_data["image_filename"]
                    dest_image = images_dir / f"{gallery_run_id}.png"

                    if source_image.exists():
                        if symlink_images and not dest_image.exists():
                            try:
                                os.symlink(source_image, dest_image)
                            except OSError:
                                # Fall back to copy if symlink fails
                                if copy_images:
                                    shutil.copy2(source_image, dest_image)
                        elif copy_images and not dest_image.exists():
                            shutil.copy2(source_image, dest_image)

                        run_data["image_path"] = f"images/{gallery_run_id}.png"

    # Merge with legacy metadata if provided
    if legacy_metadata_path and legacy_metadata_path.exists():
        legacy_data = load_json(legacy_metadata_path)
        if legacy_data:
            # Add runs from legacy data that aren't already in new structure
            if "run_specific_info" in legacy_data:
                for run_id, run_info in legacy_data["run_specific_info"].items():
                    if run_id not in gallery_data["runs"]:
                        # Convert legacy format to new format
                        colors_list = run_info.get("colors", [])
                        colors_dict = {f"Category {i+1}": c for i, c in enumerate(colors_list)}

                        legacy_run = {
                            "gallery_run_id": run_id,
                            "dataset_name": run_info.get("dataset_name", "unknown"),
                            "run_id": run_id,
                            "algorithm_type": "phate",
                            "label_key": run_info.get("label_key", "unknown"),
                            "n_categories": run_info.get("num_categories", len(colors_list)),
                            "colors": colors_dict,
                            "categories": list(colors_dict.keys()),
                            "image_path": f"images/{run_id}.png",
                            "has_image": True,  # Assume images exist
                            "source": "wandb_legacy",
                            "subtitle": run_info.get("subtitle", ""),
                        }

                        gallery_data["runs"][run_id] = legacy_run

                        # Add to datasets
                        ds_name = run_info.get("dataset_name", "unknown")
                        if ds_name not in gallery_data["datasets"]:
                            gallery_data["datasets"][ds_name] = {
                                "name": ds_name,
                                "runs": [],
                            }
                        gallery_data["datasets"][ds_name]["runs"].append(run_id)

    # Calculate summary stats
    total_runs = len(gallery_data["runs"])
    total_datasets = len(gallery_data["datasets"])
    algorithm_counts = {}
    label_key_counts = {}

    for run_data in gallery_data["runs"].values():
        algo = run_data.get("algorithm_type", "unknown")
        algorithm_counts[algo] = algorithm_counts.get(algo, 0) + 1

        label_key = run_data.get("label_key", "unknown")
        label_key_counts[label_key] = label_key_counts.get(label_key, 0) + 1

    gallery_data["summary"] = {
        "total_runs": total_runs,
        "total_datasets": total_datasets,
        "algorithm_counts": algorithm_counts,
        "label_key_counts": label_key_counts,
    }

    return gallery_data


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate gallery data from PHATE results"
    )
    parser.add_argument(
        "--phate-results-dir",
        type=Path,
        default=Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/"),
        help="Path to PHATE results directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent.parent / "gallery" / "deployed",
        help="Output directory for gallery_data.json",
    )
    parser.add_argument(
        "--legacy-metadata",
        type=Path,
        default=None,
        help="Path to existing gallery_data.json with legacy WandB metadata",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="Copy images instead of creating symlinks",
    )
    parser.add_argument(
        "--no-symlinks",
        action="store_true",
        help="Don't create symlinks to images",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    print(f"Scanning PHATE results directory: {args.phate_results_dir}")
    print(f"Output directory: {args.output_dir}")

    gallery_data = generate_gallery_data(
        phate_results_dir=args.phate_results_dir,
        output_dir=args.output_dir,
        legacy_metadata_path=args.legacy_metadata,
        copy_images=args.copy_images,
        symlink_images=not args.no_symlinks,
    )

    # Write gallery_data.json
    output_path = args.output_dir / "gallery_data_new.json"
    with open(output_path, 'w') as f:
        json.dump(gallery_data, f, indent=2)

    print(f"\nGenerated gallery data:")
    print(f"  - Total datasets: {gallery_data['summary']['total_datasets']}")
    print(f"  - Total runs: {gallery_data['summary']['total_runs']}")
    print(f"  - Algorithms: {gallery_data['summary']['algorithm_counts']}")
    print(f"  - Label keys: {len(gallery_data['summary']['label_key_counts'])} unique")
    print(f"\nOutput written to: {output_path}")

    if args.verbose:
        print("\nDatasets:")
        for ds_name, ds_info in sorted(gallery_data["datasets"].items()):
            print(f"  {ds_name}: {len(ds_info['runs'])} runs")


if __name__ == "__main__":
    main()
