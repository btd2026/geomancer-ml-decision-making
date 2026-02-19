#!/usr/bin/env python3
"""
Centralized Preprocessing Pipeline for Geomancer.

This module handles all data preprocessing steps before running experiments:
1. Data format conversion to H5AD (AnnData format)
2. Metadata validation and enrichment
3. Dataset subsampling for memory management
4. Quality control and reporting

The preprocessing pipeline ensures all data is in a consistent format
for downstream dimensionality reduction experiments.
"""

import json
import h5py
import numpy as np
import pandas as pd
import scanpy as sc
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
import argparse
import sys


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing pipeline."""
    max_cells: int = 50000
    seed: int = 42
    min_cells: int = 100  # Filter out datasets with fewer cells
    min_genes: int = 100  # Filter out cells with fewer genes
    target_sum: Optional[int] = None  # For normalization
    log_normalize: bool = True
    highly_variable_genes: Optional[int] = None  # Number of HVGs to select

    # Metadata requirements
    require_categorical: bool = True  # Require at least one categorical column
    suggest_label_columns: bool = True  # Auto-suggest best label column

    # Output options
    copy_raw: bool = True  # Keep raw data in .raw
    compression: str = "gzip"  # H5AD compression


@dataclass
class PreprocessingReport:
    """Report of preprocessing results."""
    input_file: Path
    output_file: Optional[Path] = None
    status: str = "pending"  # pending, success, skipped, error
    error_message: Optional[str] = None

    # Input statistics
    input_n_cells: int = 0
    input_n_genes: int = 0
    input_has_raw: bool = False

    # Output statistics
    output_n_cells: int = 0
    output_n_genes: int = 0
    subsampled: bool = False
    normalized: bool = False

    # Metadata info
    categorical_columns: List[str] = field(default_factory=list)
    suggested_label_key: Optional[str] = None
    n_categories: Dict[str, int] = field(default_factory=dict)

    # Timing
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    processing_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_file": str(self.input_file),
            "output_file": str(self.output_file) if self.output_file else None,
            "status": self.status,
            "error_message": self.error_message,
            "input_n_cells": self.input_n_cells,
            "input_n_genes": self.input_n_genes,
            "output_n_cells": self.output_n_cells,
            "output_n_genes": self.output_n_genes,
            "subsampled": self.subsampled,
            "normalized": self.normalized,
            "categorical_columns": self.categorical_columns,
            "suggested_label_key": self.suggested_label_key,
            "n_categories": self.n_categories,
            "timestamp": self.timestamp,
            "processing_time_seconds": self.processing_time_seconds,
        }


class DataConverter:
    """Convert various data formats to H5AD (AnnData format)."""

    @staticmethod
    def from_csv(
        matrix_path: Path,
        metadata_path: Optional[Path] = None,
        index_col: int = 0,
    ) -> sc.AnnData:
        """
        Convert CSV files to AnnData.

        Args:
            matrix_path: Path to CSV with cell × gene matrix
            metadata_path: Optional path to CSV with cell metadata
            index_col: Column to use as index (default: 0)

        Returns:
            AnnData object
        """
        # Load expression matrix
        X = pd.read_csv(matrix_path, index_col=index_col)

        # Create AnnData
        adata = sc.AnnData(X=X)

        # Add metadata if provided
        if metadata_path and metadata_path.exists():
            metadata = pd.read_csv(metadata_path, index_col=index_col)
            # Align metadata with cells
            common_cells = adata.obs_names.intersection(metadata.index)
            if len(common_cells) < len(adata.obs_names):
                print(f"  Warning: Only {len(common_cells)}/{len(adata.obs_names)} "
                      f"cells have metadata")
            adata.obs = metadata.loc[adata.obs_names]

        return adata

    @staticmethod
    def from_txt(
        matrix_path: Path,
        metadata_path: Optional[Path] = None,
        delimiter: str = "\t",
    ) -> sc.AnnData:
        """Convert TXT/TSV files to AnnData."""
        X = pd.read_csv(matrix_path, sep=delimiter, index_col=0)
        adata = sc.AnnData(X=X)

        if metadata_path and metadata_path.exists():
            metadata = pd.read_csv(metadata_path, sep=delimiter, index_col=0)
            adata.obs = metadata.loc[adata.obs_names]

        return adata

    @staticmethod
    def from_npy(
        matrix_path: Path,
        metadata_path: Optional[Path] = None,
        gene_names: Optional[List[str]] = None,
        cell_names: Optional[List[str]] = None,
    ) -> sc.AnnData:
        """
        Convert numpy arrays to AnnData.

        Args:
            matrix_path: Path to .npy file (cells × genes)
            metadata_path: Optional path to metadata CSV
            gene_names: Optional list of gene names
            cell_names: Optional list of cell barcodes

        Returns:
            AnnData object
        """
        X = np.load(matrix_path)

        gene_names = gene_names or [f"gene_{i}" for i in range(X.shape[1])]
        cell_names = cell_names or [f"cell_{i}" for i in range(X.shape[0])]

        adata = sc.AnnData(
            X=X,
            var=pd.DataFrame(index=gene_names),
            obs=pd.DataFrame(index=cell_names),
        )

        if metadata_path and metadata_path.exists():
            metadata = pd.read_csv(metadata_path, index_col=0)
            adata.obs = metadata.loc[adata.obs_names]

        return adata

    @staticmethod
    def from_10x(
        matrix_path: Path,
        metadata_path: Optional[Path] = None,
    ) -> sc.AnnData:
        """
        Convert 10x Genomics format to AnnData.

        Args:
            matrix_path: Path to matrix.mtx file or directory
            metadata_path: Optional path to cell barcode metadata

        Returns:
            AnnData object
        """
        import scipy.io as sio

        # Check if path is directory or file
        if matrix_path.is_dir():
            # Look for 10x files
            matrix_file = matrix_path / "matrix.mtx"
            genes_file = matrix_path / "genes.tsv"
            barcodes_file = matrix_path / "barcodes.tsv"
        else:
            matrix_file = matrix_path
            genes_file = matrix_path.parent / "genes.tsv"
            barcodes_file = matrix_path.parent / "barcodes.tsv"

        # Load matrix
        matrix = sio.mmread(matrix_file).T.tocsr()

        # Load genes
        if genes_file.exists():
            genes = pd.read_csv(
                genes_file,
                sep="\t" if matrix_path.is_dir() else ",",
                header=None,
                index_col=1,
            ).index
        else:
            genes = [f"gene_{i}" for i in range(matrix.shape[1])]

        # Load barcodes
        if barcodes_file.exists():
            barcodes = pd.read_csv(
                barcodes_file,
                sep="\t" if matrix_path.is_dir() else ",",
                header=None,
                index_col=0,
            ).index
        else:
            barcodes = [f"cell_{i}" for i in range(matrix.shape[0])]

        adata = sc.AnnData(
            X=matrix,
            var=pd.DataFrame(index=genes),
            obs=pd.DataFrame(index=barcodes),
        )

        if metadata_path and metadata_path.exists():
            metadata = pd.read_csv(metadata_path, index_col=0)
            adata.obs = metadata.loc[adata.obs_names]

        return adata

    @staticmethod
    def auto_detect(input_path: Path) -> Optional[sc.AnnData]:
        """
        Auto-detect file format and convert to AnnData.

        Supported formats: h5ad, csv, txt, tsv, npy, mtx, 10x directory
        """
        suffix = input_path.suffix.lower()

        try:
            if suffix == ".h5ad":
                return sc.read_h5ad(input_path)

            elif suffix == ".csv":
                return DataConverter.from_csv(input_path)

            elif suffix in [".txt", ".tsv"]:
                return DataConverter.from_txt(input_path, delimiter="\t")

            elif suffix == ".npy":
                # Look for metadata file
                metadata_path = input_path.with_suffix(".csv")
                if not metadata_path.exists():
                    metadata_path = input_path.parent / (input_path.stem + "_metadata.csv")
                return DataConverter.from_npy(input_path, metadata_path)

            elif suffix == ".mtx" or input_path.is_dir():
                # Check for 10x format
                return DataConverter.from_10x(input_path)

            else:
                raise ValueError(f"Unsupported file format: {suffix}")

        except Exception as e:
            print(f"Error converting {input_path}: {e}")
            return None


class MetadataValidator:
    """Validate and enrich metadata for AnnData objects."""

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

    @staticmethod
    def get_categorical_columns(adata: sc.AnnData) -> List[str]:
        """Get all categorical columns in obs."""
        categorical = []
        for col in adata.obs.columns:
            col_data = adata.obs[col]
            # Check if categorical or string-like
            if isinstance(col_data.dtype, pd.CategoricalDtype):
                categorical.append(col)
            elif col_data.dtype == 'object':
                # Check if it's actually categorical (few unique values)
                n_unique = col_data.nunique()
                if n_unique < min(100, len(adata) / 10):  # Heuristic
                    categorical.append(col)
        return categorical

    @staticmethod
    def count_categories(adata: sc.AnnData, col: str) -> int:
        """Count unique categories in a column."""
        col_data = adata.obs[col]
        if isinstance(col_data.dtype, pd.CategoricalDtype):
            return len(col_data.cat.categories)
        return col_data.nunique()

    @staticmethod
    def suggest_label_key(adata: sc.AnnData, min_categories: int = 2,
                          max_categories: int = 100) -> Optional[str]:
        """
        Suggest the best label key for visualization.

        Searches in priority order: condition, stages, celltype, time, cluster
        """
        categorical_cols = MetadataValidator.get_categorical_columns(adata)

        for category, columns in MetadataValidator.PRIORITY_COLUMNS.items():
            for col in columns:
                if col in categorical_cols:
                    n_cats = MetadataValidator.count_categories(adata, col)
                    if min_categories <= n_cats <= max_categories:
                        return col

        # Fallback: first categorical with reasonable categories
        for col in categorical_cols:
            n_cats = MetadataValidator.count_categories(adata, col)
            if min_categories <= n_cats <= max_categories:
                return col

        return None

    @staticmethod
    def validate(adata: sc.AnnData, config: PreprocessingConfig) -> Tuple[bool, List[str]]:
        """
        Validate AnnData meets requirements.

        Returns:
            (is_valid, list_of_warnings)
        """
        warnings = []

        # Check minimum cells
        if adata.n_obs < config.min_cells:
            warnings.append(f"Too few cells: {adata.n_obs} < {config.min_cells}")
            return False, warnings

        # Check minimum genes
        if adata.n_vars < config.min_genes:
            warnings.append(f"Too few genes: {adata.n_vars} < {config.min_genes}")
            return False, warnings

        # Check for categorical columns
        categorical = MetadataValidator.get_categorical_columns(adata)
        if config.require_categorical and not categorical:
            warnings.append("No categorical metadata columns found")
            if config.suggest_label_columns:
                suggested = MetadataValidator.suggest_label_key(adata)
                if suggested:
                    warnings.append(f"Suggested label key: {suggested}")
                else:
                    return False, warnings

        return True, warnings

    @staticmethod
    def enrich(adata: sc.AnnData) -> sc.AnnData:
        """Add standard metadata columns if missing."""
        # Add dataset_id if missing
        if "dataset_id" not in adata.obs.columns:
            adata.obs["dataset_id"] = adata.obs_names

        # Add n_genes_per_cell if missing
        if "n_genes" not in adata.obs.columns:
            adata.obs["n_genes"] = (adata.X > 0).sum(axis=1).A1 if hasattr(adata.X, "sum") else (adata.X > 0).sum(axis=1)

        # Add n_cells_per_gene if missing
        if "n_cells" not in adata.var.columns:
            adata.var["n_cells"] = (adata.X > 0).sum(axis=0).A1 if hasattr(adata.X, "sum") else (adata.X > 0).sum(axis=0)

        return adata


class DatasetSubsampler:
    """Subsample large datasets to manageable size."""

    @staticmethod
    def subsample(
        adata: sc.AnnData,
        max_cells: int,
        seed: int = 42,
        stratify_by: Optional[str] = None,
    ) -> Tuple[sc.AnnData, np.ndarray]:
        """
        Subsample dataset to max_cells.

        Args:
            adata: AnnData object
            max_cells: Maximum number of cells to keep
            seed: Random seed for reproducibility
            stratify_by: Column name for stratified sampling

        Returns:
            (subsampled_adata, indices_used)
        """
        if adata.n_obs <= max_cells:
            return adata, np.arange(adata.n_obs)

        np.random.seed(seed)

        if stratify_by and stratify_by in adata.obs.columns:
            # Stratified sampling
            indices = DatasetSubsampler._stratified_indices(
                adata, stratify_by, max_cells, seed
            )
        else:
            # Random sampling
            indices = np.random.choice(adata.n_obs, size=max_cells, replace=False)
            indices = np.sort(indices)  # Keep order

        return adata[indices].copy(), indices

    @staticmethod
    def _stratified_indices(
        adata: sc.AnnData,
        stratify_by: str,
        n_samples: int,
        seed: int,
    ) -> np.ndarray:
        """Get indices for stratified sampling."""
        labels = adata.obs[stratify_by]
        unique_labels = labels.unique()
        indices_per_label = int(n_samples / len(unique_labels))

        selected_indices = []
        np.random.seed(seed)

        for label in unique_labels:
            mask = labels == label
            label_indices = np.where(mask)[0]

            if len(label_indices) <= indices_per_label:
                selected_indices.extend(label_indices)
            else:
                sampled = np.random.choice(
                    label_indices, size=indices_per_label, replace=False
                )
                selected_indices.extend(sampled)

        # Fill remaining slots randomly
        while len(selected_indices) < n_samples:
            remaining = n_samples - len(selected_indices)
            available = np.setdiff1d(np.arange(adata.n_obs), selected_indices)
            additional = np.random.choice(available, size=min(remaining, len(available)), replace=False)
            selected_indices.extend(additional)

        return np.sort(np.array(selected_indices))[:n_samples]


class QualityControl:
    """Quality control and normalization for AnnData objects."""

    @staticmethod
    def filter_cells(
        adata: sc.AnnData,
        min_genes: int = 200,
        max_genes: Optional[int] = None,
        max_mito_percent: Optional[float] = None,
    ) -> sc.AnnData:
        """
        Filter cells based on QC metrics.

        Args:
            adata: AnnData object
            min_genes: Minimum number of genes per cell
            max_genes: Maximum number of genes per cell (for doublet detection)
            max_mito_percent: Maximum mitochondrial gene percentage

        Returns:
            Filtered AnnData (cells are filtered in place)
        """
        # Calculate QC metrics if not present
        if "n_genes" not in adata.obs.columns:
            adata.obs["n_genes"] = (adata.X > 0).sum(axis=1).A1 if hasattr(adata.X, "sum") else (adata.X > 0).sum(axis=1)

        # Filter by gene count
        sc.pp.filter_cells(adata, min_genes=min_genes)
        if max_genes:
            adata = adata[adata.obs["n_genes"] < max_genes].copy()

        # Filter by mitochondrial percentage if requested
        if max_mito_percent is not None:
            adata.var['mt'] = adata.var_names.str.startswith('MT-')
            sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
            adata = adata[adata.obs['pct_counts_mt'] < max_mito_percent].copy()

        return adata

    @staticmethod
    def filter_genes(
        adata: sc.AnnData,
        min_cells: int = 3,
    ) -> sc.AnnData:
        """
        Filter genes that appear in too few cells.

        Args:
            adata: AnnData object
            min_cells: Minimum number of cells a gene must appear in

        Returns:
            Filtered AnnData (genes are filtered in place)
        """
        sc.pp.filter_genes(adata, min_cells=min_cells)
        return adata

    @staticmethod
    def normalize(
        adata: sc.AnnData,
        target_sum: Optional[int] = 1e4,
        log_normalize: bool = True,
        highly_variable_genes: Optional[int] = None,
    ) -> sc.AnnData:
        """
        Normalize and optionally log-transform.

        Args:
            adata: AnnData object
            target_sum: Target sum for normalization (None to skip)
            log_normalize: Whether to log1p transform
            highly_variable_genes: Number of HVGs to select (None to skip)

        Returns:
            Normalized AnnData
        """
        # Store raw data if requested
        adata.raw = adata

        # Normalize
        if target_sum is not None:
            sc.pp.normalize_total(adata, target_sum=target_sum)

        # Log transform
        if log_normalize:
            sc.pp.log1p(adata)

        # Select highly variable genes
        if highly_variable_genes:
            sc.pp.highly_variable_genes(
                adata,
                n_top_genes=highly_variable_genes,
                flavor='seurat_v3'
            )
            adata = adata[:, adata.var.highly_variable].copy()

        return adata


class PreprocessingPipeline:
    """Complete preprocessing pipeline for any data type."""

    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """
        Initialize preprocessing pipeline.

        Args:
            config: Preprocessing configuration (uses defaults if None)
        """
        self.config = config or PreprocessingConfig()
        self.reports: List[PreprocessingReport] = []

    def process_file(
        self,
        input_path: Path,
        output_path: Path,
        skip_existing: bool = True,
        stratify_by: Optional[str] = None,
    ) -> PreprocessingReport:
        """
        Process a single file through the complete pipeline.

        Steps:
        1. Convert to H5AD (if needed)
        2. Validate metadata
        3. Filter cells/genes (QC)
        4. Subsample if too large
        5. Normalize
        6. Save output

        Args:
            input_path: Path to input file
            output_path: Path to output H5AD file
            skip_existing: Skip if output already exists
            stratify_by: Column for stratified subsampling

        Returns:
            PreprocessingReport with results
        """
        import time
        start_time = time.time()

        report = PreprocessingReport(
            input_file=input_path,
            output_file=output_path,
        )

        # Check if output exists
        if skip_existing and output_path.exists():
            report.status = "skipped"
            return report

        try:
            print(f"\n{'='*60}")
            print(f"Processing: {input_path.name}")
            print(f"{'='*60}")

            # Step 1: Convert to H5AD
            print("Step 1: Converting to H5AD...")
            adata = DataConverter.auto_detect(input_path)
            if adata is None:
                raise ValueError("Failed to convert input file")

            report.input_n_cells = adata.n_obs
            report.input_n_genes = adata.n_vars
            report.input_has_raw = adata.raw is not None
            print(f"  Loaded: {adata.n_obs:,} cells × {adata.n_vars:,} genes")

            # Step 2: Validate and enrich metadata
            print("Step 2: Validating metadata...")
            is_valid, warnings = MetadataValidator.validate(adata, self.config)
            for warning in warnings:
                print(f"  {warning}")

            if not is_valid:
                raise ValueError(f"Validation failed: {warnings}")

            # Enrich metadata
            adata = MetadataValidator.enrich(adata)

            # Get categorical columns
            report.categorical_columns = MetadataValidator.get_categorical_columns(adata)
            for col in report.categorical_columns:
                report.n_categories[col] = MetadataValidator.count_categories(adata, col)

            # Suggest label key
            if self.config.suggest_label_columns:
                report.suggested_label_key = MetadataValidator.suggest_label_key(adata)
                if report.suggested_label_key:
                    print(f"  Suggested label key: {report.suggested_label_key}")

            # Step 3: Quality control
            print("Step 3: Quality control filtering...")
            adata = QualityControl.filter_cells(
                adata,
                min_genes=self.config.min_genes,
            )
            adata = QualityControl.filter_genes(
                adata,
                min_cells=self.config.min_cells // 10,  # Heuristic
            )
            print(f"  After filtering: {adata.n_obs:,} cells × {adata.n_vars:,} genes")

            # Step 4: Subsample if needed
            print("Step 4: Checking subsampling...")
            if adata.n_obs > self.config.max_cells:
                print(f"  Subsampling: {adata.n_obs:,} → {self.config.max_cells:,} cells")
                adata, indices = DatasetSubsampler.subsample(
                    adata,
                    max_cells=self.config.max_cells,
                    seed=self.config.seed,
                    stratify_by=stratify_by or report.suggested_label_key,
                )
                report.subsampled = True
            else:
                print(f"  No subsampling needed ({adata.n_obs:,} cells)")
                report.subsampled = False

            # Step 5: Normalize
            if self.config.log_normalize or self.config.target_sum:
                print("Step 5: Normalizing...")
                adata = QualityControl.normalize(
                    adata,
                    target_sum=self.config.target_sum,
                    log_normalize=self.config.log_normalize,
                    highly_variable_genes=self.config.highly_variable_genes,
                )
                report.normalized = True

            # Step 6: Save output
            print("Step 6: Saving...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            adata.write_h5ad(output_path, compression=self.config.compression)

            report.output_n_cells = adata.n_obs
            report.output_n_genes = adata.n_vars
            report.status = "success"

            print(f"✓ Saved to: {output_path}")
            print(f"  Final: {adata.n_obs:,} cells × {adata.n_vars:,} genes")

        except Exception as e:
            report.status = "error"
            report.error_message = str(e)
            print(f"✗ Error: {e}")

        report.processing_time_seconds = time.time() - start_time
        return report

    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        pattern: str = "*.h5ad",
        skip_existing: bool = True,
        stratify_by: Optional[str] = None,
    ) -> List[PreprocessingReport]:
        """
        Process all files in a directory.

        Args:
            input_dir: Directory containing input files
            output_dir: Directory for output H5AD files
            pattern: Glob pattern for matching files
            skip_existing: Skip if output already exists
            stratify_by: Column for stratified subsampling

        Returns:
            List of PreprocessingReport objects
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Find input files
        input_files = list(input_dir.glob(pattern))
        print(f"Found {len(input_files)} files matching '{pattern}'")

        if not input_files:
            print("No files found!")
            return []

        self.reports = []
        for i, input_path in enumerate(input_files, 1):
            print(f"\n[{i}/{len(input_files)}]")

            output_path = output_dir / input_path.name.replace(
                input_path.suffix, ".h5ad"
            )

            report = self.process_file(
                input_path,
                output_path,
                skip_existing=skip_existing,
                stratify_by=stratify_by,
            )
            self.reports.append(report)

        return self.reports

    def save_report(self, output_path: Path) -> None:
        """Save preprocessing report to JSON."""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "max_cells": self.config.max_cells,
                "seed": self.config.seed,
                "min_genes": self.config.min_genes,
                "log_normalize": self.config.log_normalize,
            },
            "files": [r.to_dict() for r in self.reports],
            "summary": {
                "total": len(self.reports),
                "success": sum(1 for r in self.reports if r.status == "success"),
                "skipped": sum(1 for r in self.reports if r.status == "skipped"),
                "error": sum(1 for r in self.reports if r.status == "error"),
            }
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"\nReport saved to: {output_path}")

    def print_summary(self) -> None:
        """Print preprocessing summary."""
        print("\n" + "="*60)
        print("PREPROCESSING SUMMARY")
        print("="*60)

        total = len(self.reports)
        success = sum(1 for r in self.reports if r.status == "success")
        skipped = sum(1 for r in self.reports if r.status == "skipped")
        error = sum(1 for r in self.reports if r.status == "error")

        print(f"Total files:     {total}")
        print(f"  Success:       {success}")
        print(f"  Skipped:       {skipped}")
        print(f"  Errors:        {error}")

        if success > 0:
            total_cells = sum(r.output_n_cells for r in self.reports if r.status == "success")
            total_genes = sum(r.output_n_genes for r in self.reports if r.status == "success")
            avg_cells = total_cells / success
            print(f"\nOutput statistics:")
            print(f"  Total cells:   {total_cells:,}")
            print(f"  Avg cells:     {avg_cells:.0f}")
            print(f"  Total genes:   {total_genes:,}")

        # Suggested label keys
        label_keys = {}
        for r in self.reports:
            if r.suggested_label_key:
                label_keys[r.suggested_label_key] = label_keys.get(r.suggested_label_key, 0) + 1

        if label_keys:
            print(f"\nSuggested label keys:")
            for key, count in sorted(label_keys.items(), key=lambda x: -x[1]):
                print(f"  {key}: {count} datasets")

        print("="*60)


def main():
    """CLI entry point for preprocessing pipeline."""
    parser = argparse.ArgumentParser(
        description="Preprocess data for Geomancer experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all H5AD files in a directory
  python -m scripts.pipeline.preprocessing preprocess-directory \\
      --input-dir /path/to/raw_data \\
      --output-dir /path/to/processed_data

  # Process a single file
  python -m scripts.pipeline.preprocessing preprocess-file \\
      --input /path/to/data.csv \\
      --output /path/to/output.h5ad \\
      --metadata /path/to/metadata.csv

  # Process with custom settings
  python -m scripts.pipeline.preprocessing preprocess-directory \\
      --input-dir /path/to/raw_data \\
      --output-dir /path/to/processed_data \\
      --max-cells 10000 \\
      --seed 123

  # Validate existing H5AD files
  python -m scripts.pipeline.preprocessing validate \\
      --input-dir /path/to/h5ad_files
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Preprocessing command")

    # Preprocess directory command
    dir_parser = subparsers.add_parser(
        "preprocess-directory",
        help="Preprocess all files in a directory"
    )
    dir_parser.add_argument(
        "--input-dir", "-i",
        type=str,
        required=True,
        help="Input directory with data files"
    )
    dir_parser.add_argument(
        "--output-dir", "-o",
        type=str,
        required=True,
        help="Output directory for H5AD files"
    )
    dir_parser.add_argument(
        "--pattern", "-p",
        type=str,
        default="*.*",
        help="File glob pattern (default: *.*)"
    )
    dir_parser.add_argument(
        "--max-cells",
        type=int,
        default=50000,
        help="Maximum cells per dataset (default: 50000)"
    )
    dir_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )
    dir_parser.add_argument(
        "--stratify-by",
        type=str,
        help="Column for stratified subsampling"
    )
    dir_parser.add_argument(
        "--report",
        type=str,
        help="Path to save JSON report"
    )
    dir_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files"
    )

    # Preprocess single file command
    file_parser = subparsers.add_parser(
        "preprocess-file",
        help="Preprocess a single file"
    )
    file_parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input file path"
    )
    file_parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Output H5AD file path"
    )
    file_parser.add_argument(
        "--metadata",
        type=str,
        help="Path to metadata CSV file"
    )
    file_parser.add_argument(
        "--max-cells",
        type=int,
        default=50000,
        help="Maximum cells (default: 50000)"
    )
    file_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing output"
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate existing H5AD files"
    )
    validate_parser.add_argument(
        "--input-dir", "-i",
        type=str,
        required=True,
        help="Directory with H5AD files"
    )
    validate_parser.add_argument(
        "--pattern", "-p",
        type=str,
        default="*.h5ad",
        help="File glob pattern (default: *.h5ad)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Create pipeline config
    config = PreprocessingConfig(
        max_cells=getattr(args, 'max_cells', 50000),
        seed=getattr(args, 'seed', 42),
    )

    pipeline = PreprocessingPipeline(config)

    if args.command == "preprocess-directory":
        reports = pipeline.process_directory(
            input_dir=Path(args.input_dir),
            output_dir=Path(args.output_dir),
            pattern=args.pattern,
            skip_existing=not args.force,
            stratify_by=getattr(args, 'stratify_by', None),
        )
        pipeline.print_summary()

        if args.report:
            pipeline.save_report(Path(args.report))

    elif args.command == "preprocess-file":
        # Handle metadata file
        input_path = Path(args.input)

        # If separate metadata file provided, we need special handling
        # For now, just use auto-detect
        report = pipeline.process_file(
            input_path=input_path,
            output_path=Path(args.output),
            skip_existing=not args.force,
        )

        print(f"\nStatus: {report.status}")
        if report.error_message:
            print(f"Error: {report.error_message}")

    elif args.command == "validate":
        # Validate existing H5AD files
        input_files = list(Path(args.input_dir).glob(args.pattern))
        print(f"Found {len(input_files)} H5AD files\n")

        all_valid = True
        for i, fpath in enumerate(input_files, 1):
            print(f"[{i}/{len(input_files)}] {fpath.name}")

            try:
                adata = sc.read_h5ad(fpath)
                is_valid, warnings = MetadataValidator.validate(adata, config)

                print(f"  Cells: {adata.n_obs:,}, Genes: {adata.n_vars:,}")

                if warnings:
                    for warning in warnings:
                        print(f"  {warning}")

                if is_valid:
                    # Show suggested label
                    suggested = MetadataValidator.suggest_label_key(adata)
                    if suggested:
                        n_cats = MetadataValidator.count_categories(adata, suggested)
                        print(f"  ✓ Suggested label: {suggested} ({n_cats} categories)")
                    else:
                        print(f"  ⚠ No suitable label key found")
                else:
                    print(f"  ✗ Validation failed")
                    all_valid = False

            except Exception as e:
                print(f"  ✗ Error: {e}")
                all_valid = False

            print()

        if all_valid:
            print("✓ All files validated successfully")
        else:
            print("✗ Some files failed validation")
            sys.exit(1)


if __name__ == "__main__":
    main()
