#!/usr/bin/env python3
"""
Preprocess ALL datasets (regardless of size) for PHATE analysis.

This ensures every dataset goes through the preprocessing pipeline
and gets proper metadata extraction and label key detection.
"""

import argparse
import json
import numpy as np
import scanpy as sc
from pathlib import Path
from typing import Optional, List, Dict, Any
import sys
import shutil


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


def preprocess_dataset(
    input_path: Path,
    output_dir: Path,
    max_cells: int = 50000,
    seed: int = 42,
    force: bool = False,
    always_copy: bool = True,  # Always process, even if small
) -> Dict[str, Any]:
    """Preprocess a single dataset - copy and optionally subsample."""
    import pandas as pd
    import time

    start_time = time.time()
    output_path = output_dir / input_path.name

    # Skip if already exists and not forcing
    if output_path.exists() and not force:
        return {
            "status": "skipped",
            "input_file": str(input_path),
            "output_file": str(output_path),
            "reason": "already exists"
        }

    try:
        print(f"Processing: {input_path.name}")
        adata = sc.read_h5ad(input_path)
        n_cells_orig = adata.n_obs
        n_genes_orig = adata.n_vars

        print(f"  Original: {n_cells_orig:,} cells × {n_genes_orig:,} genes")

        # Subsample if needed (or if always_copy is True and we want to ensure consistency)
        if n_cells_orig > max_cells:
            print(f"  Subsampling: {n_cells_orig:,} → {max_cells:,} cells")
            np.random.seed(seed)
            indices = np.random.choice(n_cells_orig, size=max_cells, replace=False)
            indices = np.sort(indices)
            adata = adata[indices, :].copy()
            subsampled = True
        else:
            # For smaller datasets, still copy to ensure they're in the preprocessed folder
            # with consistent metadata
            print(f"  Keeping all {n_cells_orig:,} cells (copying to preprocessed)")
            subsampled = False

        # Suggest label key
        import pandas as pd  # Import pandas before using pd.CategoricalDtype
        label_key = suggest_label_key(adata)
        if label_key:
            n_categories = count_categories(adata, label_key)
            print(f"  Suggested label: {label_key} ({n_categories} categories)")
        else:
            # Fallback to first categorical column
            for col in adata.obs.columns:
                if adata.obs[col].dtype == 'object' or isinstance(adata.obs[col].dtype, pd.CategoricalDtype):
                    label_key = col
                    n_categories = count_categories(adata, col)
                    print(f"  Using label: {label_key} ({n_categories} categories)")
                    break
            else:
                label_key = None
                n_categories = 0
                print(f"  Warning: No suitable label key found")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save preprocessed data
        adata.write_h5ad(output_path)

        elapsed = time.time() - start_time
        exp_name = input_path.stem

        return {
            "status": "success",
            "input_file": str(input_path),
            "output_file": str(output_path),
            "experiment_name": exp_name,
            "n_cells_original": n_cells_orig,
            "n_cells_final": adata.n_obs,
            "n_genes": adata.n_vars,
            "subsampled": subsampled,
            "label_key": label_key,
            "n_categories": n_categories,
            "processing_time_seconds": elapsed,
        }

    except Exception as e:
        print(f"✗ Error processing {input_path.name}: {e}")
        return {
            "status": "error",
            "input_file": str(input_path),
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess ALL CELLxGENE datasets through the pipeline"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/processed",
        help="Input directory with full H5AD files"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/preprocessed",
        help="Output directory for preprocessed H5AD files"
    )
    parser.add_argument(
        "--max-cells",
        type=int,
        default=50000,
        help="Maximum cells per dataset (default: 50000)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Path to save JSON report"
    )
    parser.add_argument(
        "--task-id",
        type=int,
        help="SLURM array task ID (for processing single file in array job)"
    )
    parser.add_argument(
        "--n-tasks",
        type=int,
        help="Total number of SLURM array tasks"
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    # Get all H5AD files
    all_files = sorted(list(input_dir.glob("*.h5ad")))
    n_files = len(all_files)

    print(f"Found {n_files} H5AD files")
    print(f"Max cells: {args.max_cells:,}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    # Determine file range for this task
    if args.task_id is not None and args.n_tasks is not None:
        files_per_task = (n_files + args.n_tasks - 1) // args.n_tasks
        start_idx = args.task_id * files_per_task
        end_idx = min(start_idx + files_per_task, n_files)
        files = all_files[start_idx:end_idx]
        print(f"Task {args.task_id}/{args.n_tasks}: processing files {start_idx}-{end_idx-1}")
    else:
        files = all_files

    print(f"Processing {len(files)} files...")
    print("=" * 60)

    results = []
    for i, file_path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}]")
        result = preprocess_dataset(
            file_path,
            output_dir,
            max_cells=args.max_cells,
            seed=args.seed,
            force=args.force,
            always_copy=True,  # Process all files
        )
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    error = sum(1 for r in results if r["status"] == "error")

    print(f"Success:  {success}")
    print(f"Skipped:  {skipped}")
    print(f"Errors:   {error}")
    print(f"Total:    {len(results)}")

    # Save report
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            json.dump({
                "timestamp": str(Path.cwd()),
                "input_dir": str(input_dir),
                "output_dir": str(output_dir),
                "max_cells": args.max_cells,
                "seed": args.seed,
                "results": results,
                "summary": {
                    "total": len(results),
                    "success": success,
                    "skipped": skipped,
                    "error": error,
                }
            }, f, indent=2)
        print(f"\nReport saved to: {report_path}")

    return 0 if error == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
