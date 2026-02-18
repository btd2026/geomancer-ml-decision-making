# Geomancer LLM Decision Making

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This repository contains tools for creating and managing interactive Weights & Biases (WandB) galleries to visualize PHATE embeddings of single-cell RNA sequencing datasets from CELLxGENE Census. The project focuses on:

1. **WandB Gallery Creation** - Generate interactive HTML galleries for exploring embeddings
2. **Label Category Extraction** - Use LLMs to categorize and describe cell type labels
3. **Metadata Analysis** - Extract and analyze dataset metadata
4. **Streamlit Dashboard** - Interactive web interface for data exploration

**Current Status (February 2025):**
- Interactive WandB gallery with 404 PHATE embedding runs
- 101 datasets from CELLxGENE Census (subsampled to 50K cells each)
- 4 algorithms benchmarked: PCA, UMAP, t-SNE, PHATE
- Label category extraction using Claude API
- Streamlit app for interactive exploration

---

## Table of Contents

- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Data Storage](#data-storage)
- [Development Setup](#development-setup)
- [Key Components](#key-components)
- [ManyLatents Integration](#manylatents-integration)
- [Extending the Project](#extending-the-project)
- [Contributing](#contributing)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

```bash
# Clone the repository
git clone https://github.com/btd8/geomancer-ml-decision-making.git
cd geomancer-ml-decision-making

# Install dependencies
pip install -r requirements.txt

# Set up API keys (optional, for LLM label extraction)
export ANTHROPIC_API_KEY="your-key-here"
export WANDB_API_KEY="your-wandb-key"
```

### Option 1: Streamlit Dashboard (Recommended)

```bash
# Launch the interactive dashboard
streamlit run streamlit_app.py
```

The dashboard includes:
- WandB gallery viewer with filtering and search
- Metadata analysis and exploration
- Label category visualization

### Option 2: Create WandB Gallery

```bash
# Create a new gallery from WandB runs
python create_replit_wandb_gallery.py --run-ids <run-ids>

# Extract label categories from existing runs
python extract_label_categories.py

# Update gallery with extracted labels
python update_gallery_with_labels_v2.py
```

### Option 3: Standalone Gallery Server

```bash
# Serve an existing gallery
cd wandb_gallery_replit
python standalone_server.py
```

---

## Project Structure

```
geomancer-ml-decision-making/
├── streamlit_app.py              # Main Streamlit dashboard
├── wandb_multiselect_gallery.html # Standalone HTML gallery
│
├── scripts/                      # Analysis and utility scripts
│   ├── benchmarking/             # Algorithm benchmarking scripts
│   ├── classification/           # ML model training scripts
│   ├── data_collection/          # CELLxGENE data download scripts
│   ├── llm_processing/           # LLM-based extraction scripts
│   ├── visualization/            # Gallery and plot generation
│   ├── database/                 # Database migration and inspection
│   ├── analysis/                 # Data analysis scripts
│   ├── utilities/                # Helper utilities
│   └── deprecated/               # Archived versions (do not use)
│
├── configs/                      # Configuration files
│   ├── pipeline_config.yaml      # Main pipeline configuration
│   ├── research_context.json     # Research parameters
│   └── mcp_config.json           # API settings
│
├── wandb_gallery_replit/         # Replit-deployable gallery
│   ├── index.html                # Main gallery interface
│   ├── standalone_server.py      # Local development server
│   └── serve_gallery.py          # Production server
│
├── wandb_gallery_demo/           # Demo gallery files
├── docs/                         # Documentation
├── slurm_jobs/                   # HPC job scripts
├── models/                       # Trained ML models (if any)
└── logs/                         # Execution logs
```

---

## Data Storage

All data generated or processed by this project is stored in a centralized location on the NFS share.

### Primary Data Directory

```
/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/
```

### Directory Structure

| Subdirectory | Contents |
|--------------|----------|
| `subsampled/` | Input H5AD files (101 datasets, ≤50K cells each) |
| `processed/` | Original full-size H5AD files from CELLxGENE |
| `manylatents_outputs/` | Algorithm execution results (embeddings, plots, metrics) |
| `logs/` | SLURM job logs (stdout/stderr) |

### Input Data (`subsampled/`)

Contains the H5AD files used as input for benchmarking:

```bash
/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/subsampled/
├── A_Single_Cell_Atlas_of_Mouse_White_Adipose_Tissue_a2da8d7b.h5ad
├── Blood_d86edd6a.h5ad
├── ...
└── (101 total files)
```

Each file contains:
- Cell × gene matrix (≤50,000 cells)
- Cell metadata (tissue type, organism, etc.)
- Gene names and coordinates

### Output Data (`manylatents_outputs/`)

Contains results from algorithm runs:

```bash
/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs/
├── Blood_d86edd6a/
│   ├── phate_Blood_d86edd6a.csv      # 2D embeddings
│   ├── phate_Blood_d86edd6a.png      # Scatter plot visualization
│   ├── metrics.yaml                  # Quality metrics (TSA, LID, etc.)
│   └── .hydra/                       # Config backup
└── (101 total experiment outputs)
```

### Logs (`logs/`)

SLURM job execution logs:

```bash
/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/logs/
├── phate_<JOBID>_<ARRAY_ID>.out      # Standard output
├── phate_<JOBID>_<ARRAY_ID>.err      # Standard error
└── run_results.yaml                  # Summary of all runs
```

### Accessing the Data

From scripts, the data paths are defined as:

```python
# In scripts/utilities/generate_manylatents_configs.py
DATA_DIR = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/subsampled")
OUTPUT_BASE = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs")
```

To use a different data location, modify these paths or use command-line arguments:

```bash
# Specify custom data directory
python3 scripts/utilities/generate_manylatents_configs.py \
    --data-dir /custom/path/to/h5ad/files
```

### Data Flow

```
CELLxGENE Census
    ↓ (download)
processed/ (full-size H5AD)
    ↓ (subsample to 50K cells)
subsampled/ (input for algorithms)
    ↓ (manylatents execution)
manylatents_outputs/ (embeddings, plots, metrics)
    ↓ (gallery creation)
wandb_gallery_replit/ (interactive visualization)
```

### Storage Requirements

| Directory | Approximate Size | Notes |
|-----------|------------------|-------|
| `processed/` | ~50 GB | Full datasets (not actively used) |
| `subsampled/` | ~5 GB | Working datasets (50K cells each) |
| `manylatents_outputs/` | ~2 GB | Results per run (CSV + PNG + YAML) |
| `logs/` | ~100 MB | SLURM job logs |

**Note**: The NFS share is mounted on the HPC cluster. Local development may require adjusting paths or symlinking to local storage.

---

## Development Setup

### Local Development

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/geomancer-ml-decision-making.git
   cd geomancer-ml-decision-making
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up pre-commit hooks (optional but recommended):**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

5. **Configure your environment:**
   ```bash
   # Copy example config and edit
   cp configs/research_context.json configs/research_context.local.json
   # Edit configs/research_context.local.json with your settings
   ```

### IDE Setup

The project is compatible with any Python IDE. Recommended settings:

**VS Code:**
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

**PyCharm:**
- Set project interpreter to your virtual environment
- Enable Black formatter
- Configure pytest as the test runner

---

## Key Components

### 1. Streamlit Dashboard (`streamlit_app.py`)

Multi-page interactive application featuring:
- **WandB Gallery**: Browse and filter PHATE embedding visualizations
- **Metadata Explorer**: Analyze dataset characteristics
- **Label Categories**: View LLM-extracted label groupings

**Adding a new page to Streamlit:**
```python
# In streamlit_app.py, add to the page mapping
pages = {
    "Gallery": show_gallery,
    "Metadata": show_metadata,
    "Your New Page": show_your_page  # Add your function here
}

# Define your page function
def show_your_page():
    st.title("Your New Page")
    # Your code here
```

### 2. Gallery Creation Tools

| Script | Purpose |
|--------|---------|
| `create_replit_wandb_gallery.py` | Generate WandB galleries from runs |
| `extract_label_categories.py` | Extract label categories using LLM |
| `update_gallery_with_labels_v2.py` | Update gallery with extracted labels |
| `extract_plot_colors.py` | Extract color schemes from plots |

### 3. Analysis Scripts

| Script | Purpose |
|--------|---------|
| `metadata_analyzer.py` | Analyze dataset metadata |
| `experiment_abstraction.json` | Experiment configuration |
| `debug_wandb_runs.py` | Debug WandB run issues |

---

## ManyLatents Integration

This project uses the **ManyLatents** framework for running dimensionality reduction algorithms. ManyLatents is a separate repository that provides a unified interface for benchmarking algorithms like PHATE, UMAP, t-SNE, and PCA.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Geomancer Repository                         │
│  (this repo - config generation, orchestration, visualization) │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Calls ManyLatents via subprocess
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ManyLatents Repository                       │
│  (/home/btd8/manylatents/ - algorithm implementations)          │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

| Location | Purpose |
|----------|---------|
| `/home/btd8/manylatents/` | ManyLatents framework (separate repo) |
| `/home/btd8/manylatents/cellxgene_experiments.yaml` | Master list of experiments |
| `/home/btd8/manylatents/manylatents/configs/experiment/cellxgene/` | Individual experiment configs |
| `/home/btd8/manylatents/manylatents/configs/data/cellxgene_dataset.yaml` | Data source config |
| `scripts/utilities/generate_manylatents_configs.py` | Config generator script |
| `slurm_jobs/run_manylatents_array.slurm` | SLURM array job script |
| `scripts/benchmarking/run_all_manylatents.py` | Python sequential runner |

### Workflow

```
1. Generate Configs
   └─> scripts/utilities/generate_manylatents_configs.py
       └─> Creates 101 experiment YAML files
       └─> Creates master list: cellxgene_experiments.yaml

2. Run Experiments
   └─> Option A: slurm_jobs/run_manylatents_array.slurm (HPC/cluster)
   └─> Option B: scripts/benchmarking/run_all_manylatents.py (local/sequential)
       └─> Calls: python3 -m manylatents.main experiment=cellxgene/<config_name>

3. Collect Results
   └─> Outputs saved to: /nfs/.../manylatents_outputs/<dataset_name>/
       ├── phate_<name>.csv      # Embeddings
       ├── phate_<name>.png      # Visualization
       └── metrics.yaml          # Quality metrics
```

### Config File Format

Each experiment config is a Hydra YAML file:

```yaml
# @package _global_
name: phate_<dataset_name>

defaults:
  - override /algorithms/latent: phate      # Algorithm selection
  - override /data: cellxgene_dataset       # Data source
  - override /callbacks/embedding: default  # Output callbacks
  - override /metrics: test_metric          # Evaluation metrics

seed: 42
project: cellxgene_phate

data:
  adata_path: /path/to/dataset.h5ad
  label_key: None

algorithms:
  latent:
    n_components: 2        # Output dimensions
    # knn: 5              # PHATE-specific params
    # decay: 40
    # t: "auto"
```

### Generating Configs

To generate new experiment configs for H5AD files:

```bash
# Activate the ManyLatents environment
cd /home/btd8/manylatents
source .venv/bin/activate

# Generate configs for all H5AD files in a directory
python3 /path/to/geomancer/scripts/utilities/generate_manylatents_configs.py \
    --data-dir /path/to/h5ad/files
```

**Output:**
- Individual configs in `/home/btd8/manylatents/manylatents/configs/experiment/cellxgene/`
- Master list at `/home/btd8/manylatents/cellxgene_experiments.yaml`

### Running Experiments

#### Option 1: SLURM Array Job (HPC Cluster)

```bash
# From the geomancer repository
sbatch slurm_jobs/run_manylatents_array.slurm

# Monitor progress
squeue -u $USER
tail -f /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/logs/phate_*.out
```

The SLURM script (`slurm_jobs/run_manylatents_array.slurm`):
- Reads the master experiment list
- Runs experiments in parallel (configurable via `--array`)
- Calls ManyLatents: `python3 -m manylatents.main experiment=cellxgene/<name>`

#### Option 2: Python Sequential Runner

```bash
# Run a subset for testing
python3 scripts/benchmarking/run_all_manylatents.py --start 0 --end 5 --verbose

# Run all experiments sequentially
python3 scripts/benchmarking/run_all_manylatents.py --verbose

# Run with parallel workers
python3 scripts/benchmarking/run_all_manylatents.py --parallel 4
```

#### Option 3: Run Single Experiment

```bash
cd /home/btd8/manylatents
source .venv/bin/activate

python3 -m manylatents.main \
    experiment=cellxgene/Blood_d86edd6a \
    logger=none \
    hydra.run.dir=/output/path/Blood_d86edd6a
```

### Adding a New Algorithm to ManyLatents

To benchmark a new algorithm:

1. **Add algorithm implementation** in the ManyLatents repo:
   ```bash
   cd /home/btd8/manylatents
   # Add your algorithm to manylatents/algorithms/latent/
   ```

2. **Create algorithm config** in ManyLatents:
   ```yaml
   # /home/btd8/manylatents/manylatents/configs/algorithms/latent/your_algo.yaml
   # @package algorithms/latent
   _target_: manylatents.algorithms.latent.your_algo.YourAlgoModule
   n_components: 2
   # Add algorithm-specific parameters
   ```

3. **Update experiment generator** to use your algorithm:
   ```python
   # In scripts/utilities/generate_manylatents_configs.py
   f.write("  - override /algorithms/latent: your_algo\n")  # Changed from phate
   ```

4. **Regenerate and run**:
   ```bash
   python3 scripts/utilities/generate_manylatents_configs.py
   sbatch slurm_jobs/run_manylatents_array.slurm
   ```

### Output Structure

Each experiment produces:

```
<nfs_output_dir>/<experiment_name>/
├── <algo>_<name>.csv           # Embeddings (PHATE1, PHATE2, labels)
├── <algo>_<name>.png           # 2D scatter plot
├── metrics.yaml                # Quality metrics
└── .hydra/
    ├── config.yaml             # Full config used
    └── hydra.yaml              # Hydra metadata
```

### Customization Paths

| What to Change | File Location |
|----------------|---------------|
| Algorithm parameters | Individual experiment configs |
| Data source | `/home/btd8/manylatents/manylatents/configs/data/cellxgene_dataset.yaml` |
| Output directory | SLURM script or Python runner |
| Memory/CPU limits | `slurm_jobs/run_manylatents_array.slurm` |
| Algorithm selection | Config generator script |

### Important Notes

- **ManyLatents is a separate repository** at `/home/btd8/manylatents/`
- **Configs live in ManyLatents**, not in this repository
- **This repository generates configs** and **calls ManyLatents** via subprocess
- **Hydra is used** for configuration management (`experiment=cellxgene/<name>` syntax)
- See `docs/MANYLATENTS_SETUP.md` for more detailed documentation

---

## Extending the Project

### Adding a New Algorithm (via ManyLatents)

To add a new dimensionality reduction algorithm:

1. **Add benchmarking script** in `scripts/benchmarking/`:
   ```python
   # scripts/benchmarking/run_your_algorithm.py
   import scanpy as sc
   import anndata

   def run_your_algorithm(adata: anndata.AnnData, **params):
       """Run your algorithm on the data."""
       # Your implementation here
       embeddings = your_algorithm_func(adata.X, **params)
       return embeddings
   ```

2. **Update the config** in `configs/pipeline_config.yaml`:
   ```yaml
   algorithms:
     - name: your_algorithm
       module: scripts.benchmarking.run_your_algorithm
       default_params:
         n_components: 50
   ```

3. **Add to the gallery** by updating the label extraction in `extract_label_categories.py`

### Adding a New Data Source

To support a new data source beyond CELLxGENE:

1. **Create a downloader script** in `scripts/data_collection/`:
   ```python
   # scripts/data_collection/download_from_source.py
   def download_dataset(dataset_id: str, output_dir: str):
       """Download dataset from your source."""
       # Implementation here
       return path_to_h5ad
   ```

2. **Register the source** in `configs/pipeline_config.yaml`:
   ```yaml
   data_sources:
     - name: your_source
       module: scripts.data_collection.download_from_source
       enabled: true
   ```

### Adding a New Visualization

To add a new visualization type to the Streamlit dashboard:

1. **Create visualization function** in `scripts/visualization/`:
   ```python
   # scripts/visualization/your_viz.py
   import matplotlib.pyplot as plt
   import streamlit as st

   def plot_your_visualization(data, **kwargs):
       fig, ax = plt.subplots()
       # Your plotting code here
       st.pyplot(fig)
   ```

2. **Import and use in** `streamlit_app.py`:
   ```python
   from scripts.visualization.your_viz import plot_your_visualization

   # In your page function
   plot_your_visualization(data)
   ```

### Adding a New Metric

To add a new quality metric for embeddings:

1. **Define the metric function** in `scripts/benchmarking/compute_embedding_metrics.py`:
   ```python
   def your_metric(adata, embeddings):
       """Compute your custom metric."""
       # Implementation here
       return metric_value
   ```

2. **Register in metrics registry**:
   ```python
   METRICS = {
       "tsa": compute_tsa,
       "lid": compute_lid,
       "your_metric": your_metric,  # Add here
   }
   ```

---

## Contributing

We welcome contributions! Please follow these guidelines:

### How to Contribute

1. **Check existing issues** for what needs to be done
2. **Fork the repository** and create a feature branch
3. **Make your changes** following the code style guidelines
4. **Add tests** if applicable
5. **Update documentation** as needed
6. **Submit a pull request** with a clear description

### Code Style Guidelines

- **Python**: Follow PEP 8
- **Docstrings**: Use Google-style docstrings
- **Line length**: Maximum 100 characters
- **Imports**: Group imports (stdlib, third-party, local)
- **Variable names**: Use `snake_case` for functions and variables
- **Class names**: Use `PascalCase` for classes

Example:
```python
"""Module docstring describing purpose."""

from typing import Dict, List
import pandas as pd


def process_data(data: pd.DataFrame, param: str = "default") -> Dict[str, List]:
    """Process the input data and return results.

    Args:
        data: Input dataframe with columns...
        param: Processing parameter with options...

    Returns:
        Dictionary containing processed results...

    Raises:
        ValueError: If data format is invalid
    """
    # Implementation here
    pass
```

### Testing

Add tests for new functionality in a `tests/` directory:

```python
# tests/test_your_feature.py
import pytest
from scripts.benchmarking.run_your_algorithm import run_your_algorithm


def test_your_algorithm_basic():
    """Test basic algorithm functionality."""
    # Create test data
    # Run algorithm
    # Assert expected results
    assert True
```

Run tests:
```bash
pytest tests/
```

### Pull Request Checklist

Before submitting a PR, ensure:
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation is updated
- [ ] Commit messages are clear and descriptive
- [ ] PR description explains the "why" not just the "what"

---

## Configuration

### Gallery Configuration (`gallery_config.json`)

```json
{
  "title": "PHATE Embeddings Gallery",
  "entity": "your-entity",
  "project": "your-project",
  "filters": {
    "algorithms": ["PHATE", "UMAP", "TSNE", "PCA"],
    "max_runs": 500
  }
}
```

### Research Context (`configs/research_context.json`)

Defines the research parameters including:
- Computational focus areas
- Target algorithms and frameworks
- Search criteria

### API Keys Configuration

API keys should be set via environment variables, never committed to the repo:

```bash
# For WandB integration
export WANDB_API_KEY="your-wandb-key"

# For LLM-based label extraction
export ANTHROPIC_API_KEY="your-anthropic-key"

# For NCBI/PubMed access
export NCBI_EMAIL="your@email.com"
```

Or create a `.env` file (add to `.gitignore`):
```
WANT_DB_API_KEY=your-wandb-key
ANTHROPIC_API_KEY=your-anthropic-key
NCBI_EMAIL=your@email.com
```

---

## Data Sources

### CELLxGENE Census

The project uses datasets from the CELLxGENE Census:
- **101 datasets** across various tissues and organisms
- Subsampled to **50,000 cells** each for memory efficiency
- Stored as H5AD files for processing

### Algorithms Benchmarked

| Algorithm | Description |
|-----------|-------------|
| **PHATE** | Preserves global structure in trajectory data |
| **UMAP** | Fast, good for local structure |
| **t-SNE** | Excellent local preservation |
| **PCA** | Linear baseline, very fast |

---

## Deployment

### Replit Deployment

See `REPLIT_DEPLOYMENT_GUIDE.md` for detailed instructions:

1. Copy `wandb_gallery_replit/` to Replit
2. Configure `replit.nix` with dependencies
3. Run the server

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit
streamlit run streamlit_app.py

# Or serve static gallery
cd wandb_gallery_replit && python serve_gallery.py
```

### Docker Deployment (Optional)

Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "streamlit_app.py"]
```

Build and run:
```bash
docker build -t geomancer-dashboard .
docker run -p 8501:8501 geomancer-dashboard
```

---

## Documentation

- **`REPLIT_DEPLOYMENT_GUIDE.md`** - Deploy galleries to Replit
- **`docs/ARCHITECTURE.md`** - System architecture
- **`docs/CURRENT_STATUS.md`** - Project status updates
- **`docs/MANYLATENTS_SETUP.md`** - ManyLatents framework setup
- **`docs/SUBSAMPLING_STRATEGY.md`** - Dataset subsampling approach
- **`docs/METRICS_EXPLAINED.md`** - Metric definitions
- **`docs/SLURM_GUIDE.md`** - HPC usage instructions
- **`scripts/QUICK_REFERENCE.md`** - Script reference guide

---

## Scripts Overview

### Data Collection (`scripts/data_collection/`)
- `build_database_from_cellxgene.py` - Build database from CELLxGENE
- `download_cellxgene_datasets.py` - Download datasets
- `download_geo_datasets.py` - Download from GEO

### Benchmarking (`scripts/benchmarking/`)
- `run_phate_small_datasets.py` - Run PHATE on datasets
- `compute_manylatents_metrics.py` - Compute quality metrics
- `benchmark_all_datasets.py` - Full benchmark pipeline

### Visualization (`scripts/visualization/`)
- `create_wandb_gallery.py` - Create WandB galleries
- `create_html_gallery.py` - Generate static HTML galleries
- `labeling_app.py` - Manual labeling interface

### Classification (`scripts/classification/`)
- `train_structure_classifier_v2.py` - Train ML models
- `enhanced_final_classification.py` - Production classifier
- `classify_phate_embeddings_batched.py` - Batch classification

---

## Dependencies

### Core Libraries
- **wandb** - Experiment tracking and visualization
- **streamlit** - Interactive web dashboard
- **requests** - HTTP API integration
- **tqdm** - Progress tracking

### Scientific Computing
- **pandas, numpy** - Data processing
- **scanpy, anndata** - Single-cell analysis
- **torch** - Deep learning (for advanced models)
- **matplotlib, seaborn** - Visualization

See `requirements.txt` for complete dependency list.

---

## Troubleshooting

### Gallery Not Loading
```bash
# Check gallery configuration
cat gallery_config.json

# Verify WandB credentials
export WANDB_API_KEY="your-key"
wandb login
```

### LLM Extraction Issues
```bash
# Verify Anthropic API key
echo $ANTHROPIC_API_KEY

# Check extraction logs
tail -f logs/extract_labels_*.log
```

### Import Errors
```bash
# Ensure you're in the project root
cd geomancer-ml-decision-making

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

---

## Citation

```bibtex
@misc{geomancer_llm_decision_2025,
  title={Geomancer LLM Decision Making: Interactive Visualization for Single-Cell Analysis},
  author={[Your Name]},
  year={2025},
  institution={Yale University}
}
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Contact

- **Email**: btd8@yale.edu
- **Institution**: Yale University
- **Issues**: Use GitHub Issues for bug reports and feature requests

---

## Acknowledgments

- CELLxGENE team for data access
- Anthropic for Claude API access
- WandB for experiment tracking tools
- ManyLatents framework developers
