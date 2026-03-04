#!/usr/bin/env python3
"""
Resource configuration system for SLURM jobs.

This module provides automatic resource selection based on dataset size,
with support for auto-escalation on OOM failures.

Size thresholds based on empirical testing:
- small: <50K cells -> 16GB, 30min
- medium: 50K-200K cells -> 64GB, 60min
- large: 200K-500K cells -> 128GB, 2hr
- xlarge: >500K cells -> 256GB, 25hr (week partition)

Usage:
    from utils.resource_config import ResourceConfig, get_resource_preset

    # Get preset based on cell count
    config = get_resource_preset(n_cells=150000)  # Returns 'medium'

    # Or use ResourceConfig for more control
    rc = ResourceConfig()
    preset = rc.select_preset(n_cells=150000)
    sbatch_args = rc.get_sbatch_args(preset)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResourcePreset(str, Enum):
    """Resource presets for different dataset sizes."""
    SMALL = "small"      # <50K cells
    MEDIUM = "medium"    # 50K-200K cells
    LARGE = "large"      # 200K-500K cells
    XLARGE = "xlarge"    # >500K cells or OOM recovery


@dataclass
class ResourceConfig:
    """Resource configuration for a SLURM job."""
    mem_gb: int
    cpus: int
    time_hours: int
    partition: str
    max_concurrent: int = 50  # Max concurrent array jobs

    def to_sbatch_args(self) -> list[str]:
        """Convert to sbatch command-line arguments."""
        time_str = f"{self.time_hours:02d}:00:00"
        return [
            "--mem", f"{self.mem_gb}G",
            "--cpus-per-task", str(self.cpus),
            "--time", time_str,
            "--partition", self.partition,
        ]

    def to_sbatch_dict(self) -> dict:
        """Convert to dictionary for SBATCH directives."""
        time_str = f"{self.time_hours:02d}:00:00"
        return {
            "mem": f"{self.mem_gb}G",
            "cpus-per-task": self.cpus,
            "time": time_str,
            "partition": self.partition,
        }


# Preset configurations
PRESETS: dict[ResourcePreset, ResourceConfig] = {
    ResourcePreset.SMALL: ResourceConfig(
        mem_gb=16,
        cpus=2,
        time_hours=1,
        partition="day",
        max_concurrent=50,
    ),
    ResourcePreset.MEDIUM: ResourceConfig(
        mem_gb=64,
        cpus=4,
        time_hours=2,
        partition="day",
        max_concurrent=30,
    ),
    ResourcePreset.LARGE: ResourceConfig(
        mem_gb=128,
        cpus=8,
        time_hours=6,
        partition="day",
        max_concurrent=20,
    ),
    ResourcePreset.XLARGE: ResourceConfig(
        mem_gb=256,
        cpus=12,
        time_hours=25,  # Week partition requires >=24hr
        partition="week",
        max_concurrent=10,
    ),
}

# Size thresholds (in cells)
SIZE_THRESHOLDS = {
    50_000: ResourcePreset.SMALL,
    200_000: ResourcePreset.MEDIUM,
    500_000: ResourcePreset.LARGE,
    float('inf'): ResourcePreset.XLARGE,
}


def get_resource_preset(n_cells: int) -> ResourcePreset:
    """
    Select resource preset based on number of cells.

    Args:
        n_cells: Number of cells in the dataset

    Returns:
        ResourcePreset appropriate for the dataset size
    """
    for threshold, preset in SIZE_THRESHOLDS.items():
        if n_cells < threshold:
            return preset
    return ResourcePreset.XLARGE


def get_config(preset: ResourcePreset) -> ResourceConfig:
    """Get ResourceConfig for a preset."""
    return PRESETS[preset]


def escalate_preset(current: ResourcePreset) -> Optional[ResourcePreset]:
    """
    Get the next larger preset for OOM recovery.

    Args:
        current: Current preset that failed

    Returns:
        Next larger preset, or None if already at max
    """
    escalation_order = [
        ResourcePreset.SMALL,
        ResourcePreset.MEDIUM,
        ResourcePreset.LARGE,
        ResourcePreset.XLARGE,
    ]
    try:
        idx = escalation_order.index(current)
        if idx < len(escalation_order) - 1:
            return escalation_order[idx + 1]
    except ValueError:
        pass
    return None


def estimate_memory_usage(n_cells: int, n_genes: int = 0) -> int:
    """
    Estimate memory usage in GB for a dataset.

    Rough estimates based on empirical testing:
    - Base: 1GB per 10K cells for PHATE
    - Additional: 1GB per 1M non-zero entries in matrix

    Args:
        n_cells: Number of cells
        n_genes: Number of genes (optional, for sparse matrix estimation)

    Returns:
        Estimated memory in GB
    """
    # Base memory for PHATE operations
    base_gb = n_cells / 10_000

    # Additional for sparse matrix (assume 10% density)
    if n_genes > 0:
        nnz = n_cells * n_genes * 0.1
        matrix_gb = nnz * 8 / 1e9  # 8 bytes per float64
        base_gb += matrix_gb * 2  # Safety factor

    # Safety margin
    return int(base_gb * 1.5) + 1


# Convenience function for generating SLURM scripts
def generate_sbatch_header(
    job_name: str,
    n_jobs: int,
    preset: ResourcePreset = ResourcePreset.SMALL,
    output_pattern: str = "logs/job_%a.out",
    error_pattern: str = "logs/job_%a.err",
) -> str:
    """
    Generate SBATCH header for an array job.

    Args:
        job_name: Name of the job
        n_jobs: Number of array tasks
        preset: Resource preset to use
        output_pattern: Output file pattern
        error_pattern: Error file pattern

    Returns:
        SBATCH header as string
    """
    config = get_config(preset)

    return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --array=0-{n_jobs-1}%{config.max_concurrent}
#SBATCH --mem={config.mem_gb}G
#SBATCH --cpus-per-task={config.cpus}
#SBATCH --time={config.time_hours:02d}:00:00
#SBATCH --partition={config.partition}
#SBATCH --output={output_pattern}
#SBATCH --error={error_pattern}
"""


if __name__ == "__main__":
    # Demo usage
    print("Resource Presets:")
    print("-" * 60)
    for preset, config in PRESETS.items():
        print(f"  {preset.value:8s}: {config.mem_gb:3d}GB, {config.cpus:2d} CPUs, {config.time_hours:2d}hr, {config.partition}")

    print("\nSize Thresholds:")
    print("-" * 60)
    for threshold, preset in SIZE_THRESHOLDS.items():
        if threshold == float('inf'):
            print(f"  > 500K cells -> {preset.value}")
        else:
            print(f"  < {threshold/1000:.0f}K cells -> {preset.value}")

    print("\nExample: 150K cells")
    print("-" * 60)
    preset = get_resource_preset(150_000)
    config = get_config(preset)
    print(f"  Preset: {preset.value}")
    print(f"  Config: {config}")
    print(f"  SBATCH args: {' '.join(config.to_sbatch_args())}")
