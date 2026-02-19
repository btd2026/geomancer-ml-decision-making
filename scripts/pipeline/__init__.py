"""
Pipeline infrastructure for algorithm-agnostic experiment execution.

This module provides shared components for running dimensionality reduction
experiments across multiple algorithms (PHATE, UMAP, t-SNE, Reeb, DSE, etc.).

Submodules:
- config_generator: Generate experiment configs for any algorithm
- slurm_template: Generate SLURM job scripts
- experiment_runner: Run experiments (local, SLURM, dry-run)
- preprocessing: Preprocess data before experiments (convert, validate, subsample)
- post_process: Extract metadata after experiments complete
"""

from .config_generator import AlgorithmConfigGenerator
from .slurm_template import SlurmJobGenerator
from .experiment_runner import ExperimentRunner

__all__ = [
    "AlgorithmConfigGenerator",
    "SlurmJobGenerator",
    "ExperimentRunner",
]
