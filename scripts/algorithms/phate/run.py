#!/usr/bin/env python3
"""
PHATE algorithm runner.

This module provides functionality to run PHATE dimensionality reduction
on single-cell RNA-seq datasets.
"""

import scanpy as sc
import phate
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import warnings
warnings.filterwarnings('ignore')

from ..base import AlgorithmConfig, BaseAlgorithm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PhateRunner(BaseAlgorithm):
    """Runner for PHATE dimensionality reduction."""

    def __init__(
        self,
        config: Optional[AlgorithmConfig] = None,
        db_path: Optional[Path] = None,
    ):
        """
        Initialize the PHATE runner.

        Args:
            config: PHATE configuration (uses default if not provided)
            db_path: Path to SQLite database for tracking results
        """
        if config is None:
            from .config import PHATE_CONFIG
            config = PHATE_CONFIG

        super().__init__(config)

        self.db_path = db_path

    def run_phate_on_dataset(
        self,
        h5ad_path: Path,
        dataset_id: str,
    ) -> Tuple[Optional[np.ndarray], Optional[int], Optional[int]]:
        """
        Run PHATE on a single dataset.

        Args:
            h5ad_path: Path to H5AD file
            dataset_id: Dataset identifier

        Returns:
            Tuple of (phate_coords, n_features, n_cells) or (None, None, None) on error
        """
        try:
            logger.info(f"Loading {h5ad_path.name}...")
            adata = sc.read_h5ad(h5ad_path)

            n_cells = adata.n_obs
            n_features = adata.n_vars

            logger.info(f"  Shape: {adata.shape} ({n_cells} cells, {n_features} genes)")

            # Prepare data - use .X (raw counts or normalized)
            if adata.X is None:
                logger.error(f"  No expression matrix found!")
                return None, None, None

            # Convert to dense if sparse
            if hasattr(adata.X, 'toarray'):
                X = adata.X.toarray()
            else:
                X = adata.X

            # Get PHATE parameters
            params = self.get_default_params()
            logger.info(f"  Running PHATE (k={params.get('knn')}, t={params.get('t')})...")

            phate_op = phate.PHATE(
                n_components=params.get('n_components', 2),
                knn=params.get('knn', 100),
                t=params.get('t', 12),
                decay=params.get('decay', 60),
                n_jobs=params.get('n_jobs', -1),
                verbose=0
            )

            phate_coords = phate_op.fit_transform(X)
            logger.info(f"  PHATE complete! Embedding shape: {phate_coords.shape}")

            return phate_coords, n_features, n_cells

        except Exception as e:
            logger.error(f"  Error processing {h5ad_path.name}: {e}")
            return None, None, None

    def create_plot(
        self,
        phate_coords: np.ndarray,
        dataset_name: str,
        dataset_id: str,
        n_cells: int,
        n_features: int,
        output_path: Path,
    ) -> Path:
        """
        Create a PHATE plot for a dataset.

        Args:
            phate_coords: PHATE coordinates
            dataset_name: Dataset name
            dataset_id: Dataset identifier
            n_cells: Number of cells
            n_features: Number of features
            output_path: Path to save the plot

        Returns:
            Path to saved plot
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots(figsize=(8, 8))

        # Simple scatter plot
        scatter = ax.scatter(
            phate_coords[:, 0],
            phate_coords[:, 1],
            s=3,
            alpha=0.5,
            c=phate_coords[:, 0],  # Color by PHATE1 coordinate
            cmap='viridis',
            rasterized=True
        )

        ax.set_xlabel('PHATE 1', fontsize=12)
        ax.set_ylabel('PHATE 2', fontsize=12)
        ax.set_title(f'{dataset_name}\n{n_cells:,} cells | {n_features:,} features',
                     fontsize=10, pad=10)
        ax.grid(True, alpha=0.2)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        return output_path

    def save_embedding(
        self,
        phate_coords: np.ndarray,
        output_path: Path,
    ) -> Path:
        """
        Save PHATE embedding to CSV.

        Args:
            phate_coords: PHATE coordinates
            output_path: Path to save the embedding

        Returns:
            Path to saved embedding
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(phate_coords, columns=['PHATE1', 'PHATE2'])
        df.to_csv(output_path, index=False)
        return output_path

    def update_database(
        self,
        dataset_id: str,
        n_features: int,
        plot_path: Path,
    ) -> None:
        """
        Update database with PHATE results.

        Args:
            dataset_id: Dataset identifier
            n_features: Number of features
            plot_path: Path to plot file
        """
        if self.db_path is None:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE datasets
            SET n_features = ?,
                phate_plot_path = ?,
                benchmarked = 1
            WHERE dataset_id = ?
        """, (n_features, str(plot_path), dataset_id))
        conn.commit()
        conn.close()

    def process_dataset(
        self,
        h5ad_path: Path,
        dataset_id: str,
        dataset_name: str,
        output_dir: Path,
    ) -> Dict[str, Any]:
        """
        Process a single dataset: run PHATE, create plot, save embedding.

        Args:
            h5ad_path: Path to H5AD file
            dataset_id: Dataset identifier
            dataset_name: Dataset name
            output_dir: Base output directory

        Returns:
            Dictionary with results
        """
        plots_dir = output_dir / "plots"
        embeddings_dir = output_dir / "embeddings"

        # Run PHATE
        phate_coords, n_features, n_cells = self.run_phate_on_dataset(
            h5ad_path, dataset_id
        )

        if phate_coords is None:
            return {"status": "failed", "error": "PHATE computation failed"}

        # Create plot
        plot_path = plots_dir / f"{dataset_id}.png"
        self.create_plot(
            phate_coords, dataset_name, dataset_id,
            n_cells, n_features, plot_path
        )
        logger.info(f"  Plot saved: {plot_path}")

        # Save embedding
        embedding_path = embeddings_dir / f"{dataset_id}_phate.csv"
        self.save_embedding(phate_coords, embedding_path)
        logger.info(f"  Embedding saved: {embedding_path}")

        # Update database if configured
        if self.db_path:
            self.update_database(dataset_id, n_features, plot_path)

        return {
            "status": "success",
            "dataset_id": dataset_id,
            "n_features": n_features,
            "n_cells": n_cells,
            "plot_path": str(plot_path),
            "embedding_path": str(embedding_path),
        }

    def get_experiment_configs(self, data_dir: Path) -> list:
        """
        Return list of experiment configs for PHATE.

        Args:
            data_dir: Directory containing H5AD files

        Returns:
            List of configuration dictionaries
        """
        # For PHATE, we defer to the pipeline config generator
        # This is a stub for interface compatibility
        return []

    def get_slurm_template(self) -> str:
        """Return SLURM job script template for PHATE."""
        # Import here to avoid circular dependency
        from ...pipeline.slurm_template import DEFAULT_SLURM_TEMPLATE
        return DEFAULT_SLURM_TEMPLATE


def main():
    """CLI entry point for running PHATE on datasets."""
    import argparse

    DEFAULT_DB_PATH = Path("/home/btd8/llm-paper-analyze/data/manylatents_benchmark/manylatents_datasets.db")
    DEFAULT_DATA_DIR = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_small_datasets")
    DEFAULT_OUTPUT_DIR = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_small_datasets_phate")

    parser = argparse.ArgumentParser(
        description="Run PHATE on small datasets"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help="Directory with H5AD files"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        help="Process specific dataset only"
    )

    args = parser.parse_args()

    # Create runner
    from .config import PHATE_CONFIG
    runner = PhateRunner(
        config=PHATE_CONFIG,
        db_path=Path(args.db_path),
    )

    # Setup output directories
    output_dir = Path(args.output_dir)
    plots_dir = output_dir / "plots"
    embeddings_dir = output_dir / "embeddings"
    plots_dir.mkdir(parents=True, exist_ok=True)
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    # If dataset specified, process only that one
    if args.dataset:
        h5ad_path = Path(args.data_dir) / f"{args.dataset}.h5ad"
        if not h5ad_path.exists():
            logger.error(f"Dataset not found: {h5ad_path}")
            return

        result = runner.process_dataset(
            h5ad_path,
            args.dataset,
            args.dataset,
            output_dir,
        )
        print(f"Result: {result}")
        return

    # Otherwise process all datasets from database
    if not Path(args.db_path).exists():
        logger.error(f"Database not found: {args.db_path}")
        return

    conn = sqlite3.connect(args.db_path)
    df = pd.read_sql_query("""
        SELECT dataset_id, dataset_name
        FROM datasets
        WHERE downloaded = 1
        ORDER BY dataset_id
    """, conn)
    conn.close()

    logger.info(f"Processing {len(df)} datasets")

    results = []
    for idx, row in df.iterrows():
        dataset_id = row['dataset_id']
        dataset_name = row['dataset_name']

        # Get h5ad_url to find the actual filename
        conn = sqlite3.connect(args.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT h5ad_url FROM datasets WHERE dataset_id = ?", (dataset_id,))
        url = cursor.fetchone()[0]
        conn.close()

        # Extract version_id from URL
        version_id = url.split('/')[-1].replace('.h5ad', '')
        h5ad_path = Path(args.data_dir) / f"{version_id}.h5ad"

        if not h5ad_path.exists():
            logger.warning(f"File not found: {h5ad_path}")
            continue

        logger.info(f"[{idx+1}/{len(df)}] Processing: {dataset_name}")
        result = runner.process_dataset(
            h5ad_path,
            dataset_id,
            dataset_name,
            output_dir,
        )
        results.append(result)


if __name__ == "__main__":
    main()
