# Preprocessing Pipeline

## Overview

The preprocessing pipeline (`scripts/pipeline/preprocessing.py`) is a centralized module that handles all data preparation steps before running experiments. It ensures all data is in a consistent format (H5AD) with proper metadata for downstream dimensionality reduction.

## Pipeline Steps

For each input file, the pipeline performs these steps in order:

### Step 1: Format Conversion
Converts various data formats to H5AD (AnnData format):
- **H5AD** - Already in correct format (loaded as-is)
- **CSV** - Cell × gene matrix with optional metadata file
- **TXT/TSV** - Tab-separated values
- **NPY** - NumPy arrays with optional metadata
- **MTX/10x** - 10x Genomics format

### Step 2: Metadata Validation
Checks that required metadata is present:
- At least one categorical column for labeling
- Suggests best label key (prioritizing: condition, stages, celltype, time, cluster)
- Enriches metadata with standard fields (dataset_id, n_genes, n_cells)

### Step 3: Quality Control
Filters low-quality cells and genes:
- Filters cells with too few genes (< 200)
- Filters genes expressed in too few cells
- Optional: mitochondrial gene percentage filtering

### Step 4: Subsampling
If dataset exceeds `max_cells` (default 50,000):
- Randomly samples cells while preserving distribution
- Option for stratified sampling by label column
- Sorted indices for reproducibility

### Step 5: Normalization
- Total count normalization (default: 10,000 per cell)
- Log1p transformation
- Optional: Highly variable gene selection

### Step 6: Output
Saves processed H5AD file with:
- All preprocessing steps applied
- Report with statistics and suggested label key

## Usage

### Command Line Interface

#### Preprocess a Directory

```bash
python -m scripts.pipeline.preprocessing preprocess-directory \
    --input-dir /path/to/raw_data \
    --output-dir /path/to/processed_data \
    --pattern "*.h5ad" \
    --max-cells 50000 \
    --seed 42 \
    --report preprocessing_report.json
```

#### Preprocess a Single File

```bash
python -m scripts.pipeline.preprocessing preprocess-file \
    --input /path/to/data.csv \
    --output /path/to/output.h5ad \
    --metadata /path/to/metadata.csv \
    --max-cells 50000
```

#### Validate Existing H5AD Files

```bash
python -m scripts.pipeline.preprocessing validate \
    --input-dir /path/to/h5ad_files \
    --pattern "*.h5ad"
```

### Python API

```python
from scripts.pipeline.preprocessing import (
    PreprocessingPipeline,
    PreprocessingConfig,
    DataConverter,
    MetadataValidator,
)

# Create pipeline with custom config
config = PreprocessingConfig(
    max_cells=10000,
    seed=123,
    log_normalize=True,
    highly_variable_genes=2000,
)

pipeline = PreprocessingPipeline(config)

# Process directory
reports = pipeline.process_directory(
    input_dir=Path("raw_data"),
    output_dir=Path("processed_data"),
    pattern="*.csv",
)

# Print summary
pipeline.print_summary()
pipeline.save_report(Path("report.json"))
```

## Input Data Requirements

### Required

Your data must have:
1. **Numerical matrix** (cells × features)
2. **At least one categorical column** in metadata (for labels)

### Recommended Metadata Columns

| Category | Column Names | Example Values |
|----------|--------------|----------------|
| Condition | `disease`, `condition`, `status` | healthy/diseased, control/treatment |
| Stages | `development_stage`, `stage`, `lineage` | stage1, stage2, progenitor, mature |
| Cell Type | `cell_type`, `celltype` | T cell, B cell, neuron |
| Time | `Day`, `timepoint`, `time` | 0, 1, 2, day1, day2 |
| Cluster | `cluster`, `leiden`, `louvain` | 0, 1, 2, cluster_A |

## Data Format Examples

### CSV Format

**expression.csv:**
```
,GENE1,GENE2,GENE3
CELL1,5.2,0.0,3.1
CELL2,1.1,2.5,0.0
CELL3,0.0,1.2,4.3
```

**metadata.csv:**
```
,cell_type,disease,Day
CELL1,T cell,healthy,0
CELL2,B cell,diseased,1
CELL3,T cell,diseased,2
```

### Numpy Arrays

```python
import numpy as np
from scripts.pipeline.preprocessing import DataConverter

# Your data
X = np.random.rand(1000, 500)  # 1000 cells, 500 genes
metadata = {
    'cell_type': ['A'] * 500 + ['B'] * 500,
    'condition': ['control'] * 500 + ['treated'] * 500,
}

# Save for preprocessing
np.save('data.npy', X)
pd.DataFrame(metadata).to_csv('metadata.csv')
```

### Using Existing H5AD Files

If you already have H5AD files (e.g., from CELLxGENE), they can be used directly:

```bash
python -m scripts.pipeline.preprocessing preprocess-directory \
    --input-dir /path/to/existing_h5ad_files \
    --output-dir /path/to/processed_h5ad_files \
    --max-cells 50000
```

## Integration with Experiment Pipeline

After preprocessing, run experiments:

```bash
# 1. Preprocess data
python -m scripts.pipeline.preprocessing preprocess-directory \
    --input-dir /path/to/raw_data \
    --output-dir /path/to/processed_data

# 2. Generate experiment configs
python scripts/run_algorithm.py phate generate-configs \
    --data-dir /path/to/processed_data

# 3. Run experiments
python scripts/run_algorithm.py phate generate-slurm --n-jobs 100
sbatch slurm_jobs/run_phate_array.slurm
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `max_cells` | 50000 | Maximum cells per dataset |
| `seed` | 42 | Random seed for reproducibility |
| `min_cells` | 100 | Minimum cells required |
| `min_genes` | 100 | Minimum genes per cell |
| `target_sum` | 1e4 | Normalization target sum |
| `log_normalize` | True | Apply log1p transform |
| `highly_variable_genes` | None | Number of HVGs to select |
| `compression` | gzip | H5AD compression type |

## Output Report

The pipeline generates a JSON report with:

```json
{
  "timestamp": "2025-02-19T...",
  "config": {
    "max_cells": 50000,
    "seed": 42
  },
  "files": [
    {
      "input_file": "/path/to/input.csv",
      "output_file": "/path/to/output.h5ad",
      "status": "success",
      "input_n_cells": 100000,
      "output_n_cells": 50000,
      "subsampled": true,
      "suggested_label_key": "disease",
      "n_categories": {"disease": 2, "cell_type": 10}
    }
  ],
  "summary": {
    "total": 10,
    "success": 8,
    "skipped": 1,
    "error": 1
  }
}
```

## Troubleshooting

### No categorical columns found

Add categorical metadata to your data:
```python
adata.obs['category'] = pd.Categorical(categories)
```

### Out of memory during conversion

Reduce `max_cells` or process files individually:
```bash
python -m scripts.pipeline.preprocessing preprocess-file \
    --input large_file.csv \
    --output large_file.h5ad \
    --max-cells 10000
```

### Import errors

Install required packages:
```bash
pip install scanpy h5py pandas numpy anndata
```
