#!/usr/bin/env python3
"""
Base classes for algorithm implementations.

This module defines the interface that all algorithm implementations must follow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List


@dataclass
class AlgorithmConfig:
    """Configuration for an algorithm."""

    name: str
    """Display name of the algorithm (e.g., "PHATE", "UMAP")"""

    manylatents_key: str
    """Key used in ManyLatents config (e.g., "phate", "umap", "tsne")"""

    default_params: Dict[str, Any] = field(default_factory=dict)
    """Default algorithm parameters"""

    resource_requirements: Dict[str, Any] = field(default_factory=lambda: {
        'mem': '32G',
        'cpus': 4,
        'time': '4:00:00',
        'partition': 'day',
    })
    """SLURM resource requirements"""

    description: str = ""
    """Human-readable description of the algorithm"""

    embedding_key: str = "X_"
    """Key for embedding in AnnData object (will be combined with manylatents_key)"""

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AlgorithmConfig":
        """Create config from dictionary."""
        return cls(
            name=config.get("name", ""),
            manylatents_key=config.get("manylatents_key", ""),
            default_params=config.get("default_params", {}),
            resource_requirements=config.get(
                "resource_requirements",
                {'mem': '32G', 'cpus': 4, 'time': '4:00:00', 'partition': 'day'}
            ),
            description=config.get("description", ""),
            embedding_key=config.get("embedding_key", "X_"),
        )


class BaseAlgorithm(ABC):
    """
    Base class for algorithm implementations.

    Subclasses must implement the abstract methods to provide algorithm-specific
    behavior while inheriting common functionality.
    """

    def __init__(self, config: AlgorithmConfig):
        """
        Initialize the algorithm.

        Args:
            config: Algorithm configuration
        """
        self.config = config

    @property
    def name(self) -> str:
        """Get algorithm name."""
        return self.config.name

    @property
    def key(self) -> str:
        """Get ManyLatents key."""
        return self.config.manylatents_key

    @property
    def embedding_key(self) -> str:
        """Get full embedding key for AnnData (e.g., "X_phate")."""
        return f"{self.config.embedding_key}{self.config.manylatents_key}"

    def get_default_params(self) -> Dict[str, Any]:
        """Get default algorithm parameters."""
        return self.config.default_params.copy()

    def get_resource_requirements(self) -> Dict[str, Any]:
        """Get SLURM resource requirements."""
        return self.config.resource_requirements.copy()


# Add methods to AlgorithmConfig for convenience
def _algorithm_config_get_default_params(self) -> Dict[str, Any]:
    """Get default algorithm parameters."""
    return self.default_params.copy()


def _algorithm_config_get_resource_requirements(self) -> Dict[str, Any]:
    """Get SLURM resource requirements."""
    return self.resource_requirements.copy()


# Monkey-patch methods onto AlgorithmConfig
AlgorithmConfig.get_default_params = _algorithm_config_get_default_params
AlgorithmConfig.get_resource_requirements = _algorithm_config_get_resource_requirements


class BaseAlgorithm(ABC):
    """
    Base class for algorithm implementations.

    Subclasses must implement the abstract methods to provide algorithm-specific
    behavior while inheriting common functionality.
    """

    def __init__(self, config: AlgorithmConfig):
        """
        Initialize the algorithm.

        Args:
            config: Algorithm configuration
        """
        self.config = config

    @property
    def name(self) -> str:
        """Get algorithm name."""
        return self.config.name

    @property
    def key(self) -> str:
        """Get ManyLatents key."""
        return self.config.manylatents_key

    @property
    def embedding_key(self) -> str:
        """Get full embedding key for AnnData (e.g., "X_phate")."""
        return f"{self.config.embedding_key}{self.config.manylatents_key}"

    @abstractmethod
    def get_experiment_configs(self, data_dir: Path) -> List[Dict[str, Any]]:
        """
        Return list of experiment configs for this algorithm.

        This should generate the configuration needed to run experiments
        on datasets found in data_dir.

        Args:
            data_dir: Directory containing H5AD dataset files

        Returns:
            List of configuration dictionaries for each dataset
        """

    @abstractmethod
    def get_slurm_template(self) -> str:
        """
        Return SLURM job script template.

        Returns:
            String template for SLURM job script
        """

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate algorithm parameters.

        Args:
            params: Parameters to validate

        Returns:
            True if valid, raises ValueError otherwise
        """
        # Base implementation - subclasses can override
        return True

    def get_embedding_path(self, output_dir: Path, dataset_id: str) -> Path:
        """
        Get the expected path to the embedding file.

        Args:
            output_dir: Base output directory
            dataset_id: Dataset identifier

        Returns:
            Path to embedding CSV file
        """
        return output_dir / f"{dataset_id}_{self.config.manylatents_key}.csv"

    def get_plot_path(self, output_dir: Path, dataset_id: str) -> Path:
        """
        Get the expected path to the plot file.

        Args:
            output_dir: Base output directory
            dataset_id: Dataset identifier

        Returns:
            Path to plot PNG file
        """
        return output_dir / f"{dataset_id}.png"
