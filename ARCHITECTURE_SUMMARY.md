# Geomancer ML Architecture Summary

## 1. Entrypoints

### CLI Entry Point: `scripts/run_algorithm.py`
```bash
# List available algorithms
python scripts/run_algorithm.py --list

# Generate configs for PHATE
python scripts/run_algorithm.py phate generate-configs

# Run experiments
python scripts/run_algorithm.py phate run --mode local
```

### Other Entry Points
- `scripts/pipeline/experiment_runner.py` - Direct experiment runner
- `scripts/pipeline/config_generator.py` - Config generation

---

## 2. Base Abstractions

### `scripts/algorithms/base.py`

#### `AlgorithmConfig` (dataclass)
```python
@dataclass
class AlgorithmConfig:
    name: str                      # Display name (e.g., "PHATE")
    manylatents_key: str          # Key in ManyLatents config (e.g., "phate")
    default_params: Dict[str, Any] # Algorithm parameters
    resource_requirements: Dict    # SLURM resources (mem, cpus, time)
    description: str               # Human-readable description
    embedding_key: str = "X_"      # AnnData embedding key prefix
```

#### `BaseAlgorithm` (ABC)
Abstract methods to implement:
- `get_experiment_configs(data_dir)` - Generate configs for datasets
- `get_slurm_template()` - Return SLURM job script template

### `scripts/algorithms/registry.py`

Central registry pattern:
```python
ALGORITHM_REGISTRY: Dict[str, AlgorithmConfig] = {}

def register_algorithm(config: AlgorithmConfig)
def get_algorithm(name: str) -> AlgorithmConfig
def list_algorithms() -> List[str]
```

---

## 3. Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                    │
└─────────────────────────────────────────────────────────────────────┘

1. RAW DATA (CELLxGENE Census)
   │
   └─> scripts/data_collection/download_cellxgene_datasets.py
       Output: /data/processed/*.h5ad

2. PREPROCESSING
   │
   ├─> scripts/preprocess_and_subsample.py (subsampling to 50K cells)
   └─> scripts/preprocess_all_datasets.py (full pipeline)
       Output: /data/subsampled/*.h5ad
       Auto-detects label keys by priority:
         - TIER 1: Condition (disease, health status)
         - TIER 2: Stages (developmental, disease progression)
         - TIER 3: Cell Type
         - TIER 4: Temporal (Day, timepoint)
         - TIER 5: Clusters (leiden, louvain)

3. CONFIG GENERATION
   │
   └─> scripts/pipeline/config_generator.py
       └─> AlgorithmConfigGenerator.generate_configs()
       Output: manylatents/configs/experiment/cellxgene/*.yaml
       Also: manylatents/phate_experiments.yaml

4. EXPERIMENT EXECUTION
   │
   ├─> Local: scripts/run_algorithm.py phate run --mode local
   ├─> SLURM: scripts/run_algorithm.py phate run --mode slurm
   └─> Direct: scripts/pipeline/experiment_runner.py
       └─> ExperimentRunner.run()
           Calls: python3 -m manylatents.main experiment=cellxgene/{name}
       Output: Embeddings, plots, metrics

5. RESULTS ANALYSIS
   │
   └─> streamlit_app.py (visualization)
```

---

## 4. Simplest End-to-End Example

```python
import sys
from pathlib import Path
sys.path.insert(0, "scripts")

# 1. Get algorithm configuration
from algorithms import get_algorithm
config = get_algorithm("phate")
print(f"Algorithm: {config.name}")
print(f"Params: {config.get_default_params()}")

# 2. Generate configs
from pipeline.config_generator import AlgorithmConfigGenerator

generator = AlgorithmConfigGenerator(
    algorithm_name="phate",
    manylatents_dir=Path("/path/to/manylatents"),
    data_dir=Path("/path/to/data"),
    output_base=Path("/path/to/outputs"),
)

configs = generator.generate_configs(
    algorithm_params=config.get_default_params()
)

# 3. Run experiments
from pipeline.experiment_runner import ExperimentRunner

runner = ExperimentRunner(
    algorithm="phate",
    manylatents_dir=Path("/path/to/manylatents"),
    output_base=Path("/path/to/outputs"),
)

results = runner.run(parallel=1, start=0, end=1)
```

---

## 5. Key Files Reference

| File | Purpose |
|------|---------|
| `scripts/algorithms/base.py` | Core abstractions (AlgorithmConfig, BaseAlgorithm) |
| `scripts/algorithms/registry.py` | Algorithm registry |
| `scripts/algorithms/phate/` | PHATE implementation |
| `scripts/run_algorithm.py` | Main CLI entry point |
| `scripts/pipeline/config_generator.py` | Config generation |
| `scripts/pipeline/experiment_runner.py` | Experiment execution |
| `scripts/preprocess_and_subsample.py` | Data preprocessing |

---

## 6. Current State

- **Implemented Algorithms**: PHATE only
- **Design**: Algorithm-agnostic via `BaseAlgorithm` interface
- **Execution**: Delegated to ManyLatents
- **Infrastructure**: SLURM job generation, config management, label auto-detection
