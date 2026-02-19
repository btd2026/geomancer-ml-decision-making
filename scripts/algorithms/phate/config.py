#!/usr/bin/env python3
"""
PHATE algorithm configuration.

This module defines the PHATE algorithm configuration including default
parameters and resource requirements.
"""

from ..base import AlgorithmConfig

# PHATE configuration
PHATE_CONFIG = AlgorithmConfig(
    name="PHATE",
    manylatents_key="phate",
    description=(
        "PHATE (Potential of Heat-diffusion for Affinity-based Trajectory Embedding) "
        "is a dimensionality reduction method designed for visualizing trajectory "
        "structure in high-dimensional data. It uses heat diffusion to preserve "
        "both local and global structure."
    ),
    default_params={
        'n_components': 2,
        'knn': 100,
        't': 12,
        'decay': 60,
        'n_jobs': -1,
    },
    resource_requirements={
        'mem': '32G',
        'cpus': 4,
        'time': '4:00:00',
        'partition': 'day',
    },
    embedding_key="X_",
)

# PHATE parameters for different data sizes
PHATE_PRESETS = {
    "small": {
        'n_components': 2,
        'knn': 50,
        't': 12,
        'decay': 60,
        'n_jobs': -1,
    },
    "medium": {
        'n_components': 2,
        'knn': 100,
        't': 12,
        'decay': 60,
        'n_jobs': -1,
    },
    "large": {
        'n_components': 2,
        'knn': 150,
        't': 15,
        'decay': 60,
        'n_jobs': -1,
    },
}

# Resource presets based on data size
RESOURCE_PRESETS = {
    "small": {
        'mem': '16G',
        'cpus': 2,
        'time': '1:00:00',
        'partition': 'day',
    },
    "medium": {
        'mem': '32G',
        'cpus': 4,
        'time': '4:00:00',
        'partition': 'day',
    },
    "large": {
        'mem': '64G',
        'cpus': 8,
        'time': '8:00:00',
        'partition': 'day',
    },
}


def get_phate_config(preset: str = "medium") -> AlgorithmConfig:
    """
    Get PHATE configuration with preset parameters.

    Args:
        preset: One of "small", "medium", or "large"

    Returns:
        Algorithm configuration with preset parameters
    """
    if preset not in PHATE_PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(PHATE_PRESETS.keys())}")

    return AlgorithmConfig(
        name="PHATE",
        manylatents_key="phate",
        description=PHATE_CONFIG.description,
        default_params=PHATE_PRESETS[preset],
        resource_requirements=RESOURCE_PRESETS[preset],
        embedding_key="X_",
    )
