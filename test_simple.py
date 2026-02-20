#!/usr/bin/env python3
"""
Simple end-to-end test of the Geomancer pipeline.

This demonstrates:
1. Base abstractions (AlgorithmConfig, Registry)
2. Data flow (Synthetic data -> Config -> Execution)
3. The simplest possible example
"""

import sys
from pathlib import Path

# Add scripts to path
SCRIPT_DIR = Path(__file__).parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import numpy as np
import scanpy as sc
import pandas as pd

# ============================================================================
# PART 1: BASE ABSTRACTIONS
# ============================================================================
print("=" * 70)
print("PART 1: BASE ABSTRACTIONS")
print("=" * 70)

from algorithms.base import AlgorithmConfig
from algorithms import list_algorithms, get_algorithm

# Show the base abstraction
print("\n1. AlgorithmConfig (dataclass for algorithm configuration):")
print("   Fields:")
print("     - name: Display name")
print("     - manylatents_key: Key used in ManyLatents config")
print("     - default_params: Default algorithm parameters")
print("     - resource_requirements: SLURM resources")
print("     - description: Human-readable description")

phate_config = get_algorithm("phate")
print(f"\n2. Registered PHATE algorithm:")
print(f"   - name: {phate_config.name}")
print(f"   - manylatents_key: {phate_config.manylatents_key}")
print(f"   - default_params: {phate_config.get_default_params()}")
print(f"   - resource_requirements: {phate_config.get_resource_requirements()}")

print(f"\n3. All registered algorithms: {list_algorithms()}")

# ============================================================================
# PART 2: CREATE SIMPLE TEST DATA
# ============================================================================
print("\n" + "=" * 70)
print("PART 2: CREATE TEST DATA")
print("=" * 70)

# Create a simple synthetic dataset
n_cells = 1000
n_genes = 500

# Create a simple trajectory structure
np.random.seed(42)
traj = np.linspace(0, 1, n_cells)
# Add noise to create trajectory
X = np.random.randn(n_cells, n_genes) * 0.1
# Add trajectory signal to first 50 genes
for i in range(50):
    X[:, i] += traj * np.sin(traj * 10 + i)

# Create AnnData object
adata = sc.AnnData(X)
adata.obs['trajectory_time'] = traj.astype(str)
adata.obs['cell_type'] = ['Type_A' if t < 0.5 else 'Type_B' for t in traj]

print(f"\nCreated synthetic dataset:")
print(f"  - n_cells: {adata.n_obs}")
print(f"  - n_genes: {adata.n_vars}")
print(f"  - obs columns: {list(adata.obs.columns)}")

# Save to test file
test_output_dir = Path("/tmp/geomancer_test")
test_output_dir.mkdir(exist_ok=True)
test_h5ad_path = test_output_dir / "test_dataset.h5ad"
adata.write_h5ad(test_h5ad_path)
print(f"  - Saved to: {test_h5ad_path}")

# ============================================================================
# PART 3: DATA FLOW - CONFIG GENERATION
# ============================================================================
print("\n" + "=" * 70)
print("PART 3: DATA FLOW - CONFIG GENERATION")
print("=" * 70)

from pipeline.config_generator import auto_detect_label_key

detected_label = auto_detect_label_key(test_h5ad_path)
print(f"\nAuto-detected label key: {detected_label}")

# Generate a minimal ManyLatents config
import yaml

config = {
    'name': 'phate_test_dataset',
    'defaults': [
        'override /algorithms/latent: phate',
        'override /data: cellxgene_dataset',
        'override /callbacks/embedding: default',
        'override /metrics: test_metric',
    ],
    'seed': 42,
    'project': 'phate_test',
    'data': {
        'adata_path': str(test_h5ad_path),
        'label_key': detected_label or 'cell_type',
    },
    'algorithms': {
        'latent': phate_config.get_default_params()
    }
}

config_path = test_output_dir / "test_config.yaml"
with open(config_path, 'w') as f:
    yaml.dump(config, f)

print(f"\nGenerated ManyLatents config:")
print(f"  - Path: {config_path}")
print(f"  - Content preview:")
with open(config_path) as f:
    for line in f.readlines()[:15]:
        print(f"    {line.rstrip()}")

# ============================================================================
# PART 4: SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("SUMMARY: END-TO-END DATA FLOW")
print("=" * 70)

print("""
The pipeline flow:

1. RAW DATA (H5AD files)
   ↓
2. PREPROCESSING (subsample, clean)
   ↓
3. CONFIG GENERATION (auto-detect labels, create YAML)
   ↓
4. EXPERIMENT EXECUTION (ManyLatents runs algorithm)
   ↓
5. OUTPUTS (embeddings, plots, metrics)

Base Abstractions:
  - AlgorithmConfig: Holds algorithm metadata and defaults
  - ALGORITHM_REGISTRY: Central dictionary of available algorithms
  - BaseAlgorithm: Abstract interface for algorithm implementations

Current State:
  - PHATE is the only fully implemented algorithm
  - System designed to be algorithm-agnostic
  - Integration with ManyLatents for execution
""")

print(f"\nTest artifacts saved to: {test_output_dir}/")
print("  - test_dataset.h5ad (synthetic data)")
print("  - test_config.yaml (ManyLatents config)")
