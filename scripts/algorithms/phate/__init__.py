"""
PHATE algorithm implementation.

PHATE (Potential of Heat-diffusion for Affinity-based Trajectory Embedding)
is a dimensionality reduction method designed for visualizing trajectory
structure in high-dimensional data.
"""

from .config import PHATE_CONFIG
from .run import PhateRunner

__all__ = ["PHATE_CONFIG", "PhateRunner"]
