#!/usr/bin/env python3
"""
Simple PHATE runner for H5AD files with WandB logging.

This script runs PHATE embedding on an H5AD file, saves results,
and logs metrics to WandB.
"""

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import scanpy as sc
import phate
import pandas as pd
import wandb

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# WandB project configuration
WANDB_ENTITY = "cesar-valdez-mcgill-university"
WANDB_PROJECT = "manylatent-2026-brian"


def main():
    parser = argparse.ArgumentParser(description="Run PHATE on H5AD file with WandB logging")
    parser.add_argument("h5ad_path", type=str, help="Path to H5AD file")
    parser.add_argument("output_dir", type=str, help="Output directory")
    parser.add_argument("--label-key", type=str, default="auto", help="Label key in adata.obs")
    parser.add_argument("--n-components", type=int, default=2, help="PHATE n_components")
    parser.add_argument("--knn", type=int, default=30, help="PHATE knn")
    parser.add_argument("--t", type=int, default=10, help="PHATE t")
    parser.add_argument("--decay", type=int, default=60, help="PHATE decay")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--run-name", type=str, default=None, help="WandB run name")

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get experiment name from h5ad filename for WandB run name
    h5ad_name = Path(args.h5ad_path).stem
    run_name = args.run_name or f"phate_{h5ad_name}"

    # Initialize WandB
    wandb.init(
        entity=WANDB_ENTITY,
        project=WANDB_PROJECT,
        name=run_name,
        config={
            "h5ad_path": args.h5ad_path,
            "n_components": args.n_components,
            "knn": args.knn,
            "t": args.t,
            "decay": args.decay,
            "seed": args.seed,
            "label_key": args.label_key,
        },
        tags=["phate", "single-cell", "h5ad"],
    )

    try:
        logger.info(f"Loading H5AD from {args.h5ad_path}")
        adata = sc.read_h5ad(args.h5ad_path)

        n_obs, n_vars = adata.n_obs, adata.n_vars
        logger.info(f"Data: {n_obs} cells x {n_vars} genes")

        # Log dataset info to WandB
        wandb.config.update({
            "n_cells": n_obs,
            "n_genes": n_vars,
        })

        # Detect label key
        label_key = args.label_key
        if label_key == "auto":
            common_keys = [
                "cell_type", "cell_type_ontology_term_id", "cluster", "clusters",
                "seurat_clusters", "leiden", "louvain", "SampleID",
            ]
            for key in common_keys:
                if key in adata.obs.columns:
                    labels = adata.obs[key]
                    unique = labels.unique()
                    if 2 <= len(unique) <= 500:
                        label_key = key
                        logger.info(f"Auto-detected label key: {label_key}")
                        break

        # Get label info
        n_categories = 0
        if label_key and label_key in adata.obs.columns:
            labels = adata.obs[label_key]
            value_counts = labels.value_counts()
            n_categories = len(value_counts)
            logger.info(f"Label key: {label_key}, Categories: {n_categories}")

            # Log category distribution to WandB
            category_data = {
                f"category_{i}": count
                for i, count in enumerate(value_counts.values)
            }
            wandb.log({"category_distribution": wandb.Histogram(value_counts.values)})

        # Run PHATE
        logger.info(f"Running PHATE: knn={args.knn}, t={args.t}, decay={args.decay}")
        phate_op = phate.PHATE(
            n_components=args.n_components,
            knn=args.knn,
            t=args.t,
            decay=args.decay,
            random_state=args.seed,
            n_jobs=-1,
        )

        # Handle sparse matrices
        if hasattr(adata.X, "toarray"):
            X = adata.X.toarray()
        else:
            X = adata.X

        embedding = phate_op.fit_transform(X)
        logger.info(f"PHATE embedding shape: {embedding.shape}")

        # Try to log PHATE potential (may not be available as a scalar)
        potential = phate_op_potential(phate_op)
        if potential is not None:
            if hasattr(potential, 'mean'):
                wandb.log({"phate_potential_mean": float(potential.mean())})
            elif not isinstance(potential, (list, tuple, np.ndarray)):
                wandb.log({"phate_potential": float(potential)})

        # Save embedding
        embedding_df = pd.DataFrame(
            embedding,
            columns=[f"PHATE_{i}" for i in range(embedding.shape[1])],
            index=adata.obs_names,
        )
        embedding_path = output_dir / "embedding.csv"
        embedding_df.to_csv(embedding_path)
        logger.info(f"Saved embedding to {embedding_path}")

        # Save embedding to WandB as artifact
        artifact = wandb.Artifact(name=f"{run_name}_embedding", type="embedding")
        artifact.add_file(str(embedding_path))
        wandb.log_artifact(artifact)

        # Save metadata
        metadata = {
            "n_obs": int(n_obs),
            "n_vars": int(n_vars),
            "label_key": label_key if label_key != "auto" else None,
            "n_categories": n_categories,
        }

        if label_key and label_key in adata.obs.columns:
            metadata["categories"] = [
                {"name": str(cat), "count": int(count)}
                for cat, count in value_counts.items()
            ]

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to {metadata_path}")

        # Log final summary
        wandb.log({
            "n_cells": n_obs,
            "n_genes": n_vars,
            "n_categories": n_categories,
            "embedding_dim": embedding.shape[1],
        })

        logger.info("Done!")

    finally:
        wandb.finish()


def phate_op_potential(phate_op):
    """Extract the PHATE potential if available."""
    if hasattr(phate_op, 'potential'):
        return phate_op.potential
    elif hasattr(phate_op, 'diff_potential'):
        return phate_op.diff_potential
    return None


if __name__ == "__main__":
    main()
