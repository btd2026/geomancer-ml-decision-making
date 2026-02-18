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
- [Development Setup](#development-setup)
- [Key Components](#key-components)
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
git clone https://github.com/btd8/geomancer-llm-decision-making.git
cd geomancer-llm-decision-making

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
geomancer-llm-decision-making/
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

## Development Setup

### Local Development

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/geomancer-llm-decision-making.git
   cd geomancer-llm-decision-making
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

## Extending the Project

### Adding a New Algorithm

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
cd geomancer-llm-decision-making

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
