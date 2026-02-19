#!/usr/bin/env python3
"""
Algorithm registry for managing available algorithms.

This module provides a central registry of all available algorithms,
allowing dynamic lookup and instantiation.
"""

from typing import Dict, Optional, List
from pathlib import Path

from .base import AlgorithmConfig, BaseAlgorithm


# Registry of available algorithms
ALGORITHM_REGISTRY: Dict[str, AlgorithmConfig] = {}


def register_algorithm(config: AlgorithmConfig) -> None:
    """
    Register an algorithm configuration.

    Args:
        config: Algorithm configuration to register
    """
    ALGORITHM_REGISTRY[config.manylatents_key.lower()] = config


def unregister_algorithm(key: str) -> None:
    """
    Unregister an algorithm.

    Args:
        key: Algorithm key to unregister
    """
    if key.lower() in ALGORITHM_REGISTRY:
        del ALGORITHM_REGISTRY[key.lower()]


def get_algorithm(name: str) -> AlgorithmConfig:
    """
    Get algorithm configuration by name.

    Args:
        name: Algorithm name (case-insensitive)

    Returns:
        Algorithm configuration

    Raises:
        ValueError: If algorithm not found
    """
    key = name.lower()
    if key not in ALGORITHM_REGISTRY:
        available = list(ALGORITHM_REGISTRY.keys())
        raise ValueError(
            f"Unknown algorithm: {name}. Available: {available}"
        )
    return ALGORITHM_REGISTRY[key]


def list_algorithms() -> List[str]:
    """
    Return list of available algorithm keys.

    Returns:
        List of algorithm keys (lowercase)
    """
    return list(ALGORITHM_REGISTRY.keys())


def get_algorithm_names() -> Dict[str, str]:
    """
    Return mapping of algorithm keys to display names.

    Returns:
        Dictionary mapping lowercase keys to display names
    """
    return {
        key: config.name
        for key, config in ALGORITHM_REGISTRY.items()
    }


def is_registered(name: str) -> bool:
    """
    Check if an algorithm is registered.

    Args:
        name: Algorithm name to check

    Returns:
        True if algorithm is registered
    """
    return name.lower() in ALGORITHM_REGISTRY


# Import and register built-in algorithms
def _register_builtin_algorithms() -> None:
    """Register all built-in algorithm configurations."""
    try:
        from .phate.config import PHATE_CONFIG
        register_algorithm(PHATE_CONFIG)
    except ImportError:
        # PHATE not available yet
        pass

    # Additional algorithms will be added here:
    # try:
    #     from .umap.config import UMAP_CONFIG
    #     register_algorithm(UMAP_CONFIG)
    # except ImportError:
    #     pass
    #
    # try:
    #     from .tsne.config import TSNE_CONFIG
    #     register_algorithm(TSNE_CONFIG)
    # except ImportError:
    #     pass


# Auto-register on import
_register_builtin_algorithms()
