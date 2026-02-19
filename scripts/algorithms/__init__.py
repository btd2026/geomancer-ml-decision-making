"""
Algorithm implementations for dimensionality reduction experiments.

This module provides a unified interface for running different dimensionality
reduction algorithms (PHATE, UMAP, t-SNE, Reeb, DSE, etc.) through ManyLatents.

Example:
    >>> from algorithms import get_algorithm
    >>> config = get_algorithm("phate")
    >>> print(config.name, config.default_params)
"""

from .base import AlgorithmConfig, BaseAlgorithm
from .registry import (
    get_algorithm,
    list_algorithms,
    get_algorithm_names,
    ALGORITHM_REGISTRY,
)

__all__ = [
    "AlgorithmConfig",
    "BaseAlgorithm",
    "get_algorithm",
    "list_algorithms",
    "get_algorithm_names",
    "ALGORITHM_REGISTRY",
]
