# How to Add a New Algorithm

This guide explains how to add a new dimensionality reduction algorithm to the Geomancer pipeline using the algorithm-agnostic infrastructure.

## Overview

The pipeline is organized to make adding new algorithms straightforward:

```
scripts/
├── pipeline/                   # SHARED infrastructure (use as-is)
│   ├── config_generator.py     # Generic config generation
│   ├── slurm_template.py       # SLURM job template generator
│   └── experiment_runner.py    # Generic experiment execution
│
├── algorithms/                 # ALGORITHM-SPECIFIC (add your algo here)
│   ├── base.py                 # Base interface (don't modify)
│   ├── registry.py             # Algorithm registry (add your algo)
│   ├── phate/                  # Example: PHATE algorithm
│   └── your_algorithm/         # ← Add your algorithm here
│       ├── __init__.py
│       ├── config.py
│       ├── run.py              # (optional, for direct execution)
│       └── slurm_job.slurm     # (optional, custom template)
│
└── run_algorithm.py            # Main CLI (works for all algorithms)
```

## Step-by-Step Guide

### Step 1: Create Algorithm Directory

```bash
mkdir -p scripts/algorithms/your_algorithm
```

Replace `your_algorithm` with a short identifier (e.g., `umap`, `tsne`, `reeb`, `dse`).

### Step 2: Create Configuration

Create `scripts/algorithms/your_algorithm/config.py`:

```python
#!/usr/bin/env python3
"""Your Algorithm configuration."""

from ..base import AlgorithmConfig

YOUR_ALGORITHM_CONFIG = AlgorithmConfig(
    name="Your Algorithm Display Name",
    manylatents_key="your_algorithm",  # Must match ManyLatents config key
    description=(
        "A brief description of your algorithm. "
        "Explain what it does and when to use it."
    ),
    default_params={
        'n_components': 2,
        # Add your algorithm's default parameters here
        'param1': value1,
        'param2': value2,
    },
    resource_requirements={
        'mem': '32G',      # Memory per job
        'cpus': 4,         # CPU cores per job
        'time': '4:00:00', # Wall time limit
        'partition': 'day', # SLURM partition
    },
)

# Optional: Presets for different data sizes
PRESETS = {
    "small": {
        'n_components': 2,
        'param1': small_value,
    },
    "large": {
        'n_components': 2,
        'param1': large_value,
    },
}
```

**Key fields:**
- `name`: Human-readable name (e.g., "UMAP", "t-SNE")
- `manylatents_key`: Must match the algorithm key in ManyLatents configs
- `default_params`: Parameters that go into the experiment config
- `resource_requirements`: SLURM resource allocation

### Step 3: Create Package Init File

Create `scripts/algorithms/your_algorithm/__init__.py`:

```python
"""Your Algorithm implementation."""

from .config import YOUR_ALGORITHM_CONFIG

__all__ = ["YOUR_ALGORITHM_CONFIG"]
```

### Step 4: Register the Algorithm

Edit `scripts/algorithms/registry.py` and add your import:

```python
def _register_builtin_algorithms() -> None:
    """Register all built-in algorithm configurations."""
    try:
        from .phate.config import PHATE_CONFIG
        register_algorithm(PHATE_CONFIG)
    except ImportError:
        pass

    # Add your algorithm here
    try:
        from .your_algorithm.config import YOUR_ALGORITHM_CONFIG
        register_algorithm(YOUR_ALGORITHM_CONFIG)
    except ImportError:
        pass
```

### Step 5: Verify Registration

```bash
# List all available algorithms
python scripts/run_algorithm.py --list

# Should show your algorithm:
#   your_algorithm  - Your Algorithm Display Name
```

### Step 6: Use Your Algorithm

Now you can use all pipeline features with your algorithm:

```bash
# Show algorithm info
python scripts/run_algorithm.py your_algorithm info

# Generate experiment configs
python scripts/run_algorithm.py your_algorithm generate-configs \
    --data-dir /path/to/h5ad/files

# Generate SLURM script
python scripts/run_algorithm.py your_algorithm generate-slurm \
    --n-jobs 100 \
    --mem 64G --cpus 8

# Run experiments
python scripts/run_algorithm.py your_algorithm run \
    --mode local \
    --parallel 4
```

## Optional: Custom Runner

If your algorithm needs custom execution logic (not via ManyLatents), create `scripts/algorithms/your_algorithm/run.py`:

```python
#!/usr/bin/env python3
"""Your Algorithm runner."""

from pathlib import Path
import numpy as np
from ..base import BaseAlgorithm, AlgorithmConfig

class YourAlgorithmRunner(BaseAlgorithm):
    """Runner for Your Algorithm."""

    def __init__(self, config: AlgorithmConfig = None):
        if config is None:
            from .config import YOUR_ALGORITHM_CONFIG
            config = YOUR_ALGORITHM_CONFIG
        super().__init__(config)

    def run_algorithm(self, adata, **params):
        """Run your algorithm on an AnnData object."""
        # Your implementation here
        # Return: embedding coordinates
        pass

    def get_experiment_configs(self, data_dir: Path):
        """Return experiment configs for datasets."""
        # Return list of config dicts
        pass

    def get_slurm_template(self) -> str:
        """Return SLURM template."""
        from ...pipeline.slurm_template import DEFAULT_SLURM_TEMPLATE
        return DEFAULT_SLURM_TEMPLATE
```

## Optional: Custom SLURM Template

If your algorithm has special SLURM requirements, create `scripts/algorithms/your_algorithm/slurm_job.slurm`:

```bash
#!/bash
#SBATCH --job-name={job_name}
#SBATCH --array={array_range}
#SBATCH --mem={mem}
#SBATCH --cpus-per-task={cpus}
#SBATCH --time={time}
#SBATCH --partition={partition}
#SBATCH --gpus=1  # If your algorithm needs GPUs

# Any custom setup steps
module load cuda/12.1

# Run your algorithm
python -m your_module ...
```

## Integration with ManyLatents

If your algorithm is implemented in ManyLatents:

1. Add the algorithm to ManyLatents repository
2. Create a config in `manylatents/configs/algorithms/latent/your_algorithm.yaml`
3. Set `manylatents_key="your_algorithm"` in your config

The pipeline will automatically:
- Generate experiment configs with the right algorithm override
- Create SLURM scripts with appropriate resources
- Run via ManyLatents CLI

## Testing Your Algorithm

```bash
# Test with a single dataset
python scripts/run_algorithm.py your_algorithm info

# Dry run to see what would be executed
python scripts/run_algorithm.py your_algorithm run \
    --mode local \
    --dry-run

# Test with a small subset
python scripts/run_algorithm.py your_algorithm run \
    --mode local \
    --start 0 \
    --end 2 \
    --verbose
```

## Example: Adding UMAP

Here's a complete example for adding UMAP:

**1. Create directory:**
```bash
mkdir -p scripts/algorithms/umap
```

**2. Create `config.py`:**
```python
from ..base import AlgorithmConfig

UMAP_CONFIG = AlgorithmConfig(
    name="UMAP",
    manylatents_key="umap",
    description="Uniform Manifold Approximation and Projection for dimension reduction.",
    default_params={
        'n_components': 2,
        'n_neighbors': 15,
        'min_dist': 0.1,
        'metric': 'euclidean',
    },
    resource_requirements={
        'mem': '16G',
        'cpus': 4,
        'time': '2:00:00',
        'partition': 'day',
    },
)
```

**3. Create `__init__.py`:**
```python
from .config import UMAP_CONFIG

__all__ = ["UMAP_CONFIG"]
```

**4. Update `registry.py`:**
```python
try:
    from .umap.config import UMAP_CONFIG
    register_algorithm(UMAP_CONFIG)
except ImportError:
    pass
```

**5. Use it:**
```bash
python scripts/run_algorithm.py umap generate-configs
python scripts/run_algorithm.py umap run --mode local
```

## Troubleshooting

**Algorithm not showing in `--list`:**
- Check that `registry.py` imports your config
- Verify no import errors in your config file

**Config generation fails:**
- Ensure `manylatents_key` matches ManyLatents config
- Check that data directory path is correct

**SLURM jobs fail:**
- Adjust `resource_requirements` in config
- Check ManyLatents logs for algorithm-specific errors

## Migration from Old Scripts

If you have an old algorithm-specific script:

1. Extract parameters into `config.py`
2. Move execution logic to `run.py` (if custom)
3. Register in `registry.py`
4. Delete old script from `scripts/deprecated/`

Example migration:
- Old: `scripts/benchmarking/run_phate_small_datasets.py`
- New: `scripts/algorithms/phate/run.py`
