# SLURM Job Post-Processing for Plot Metadata

## Overview

When running dimensionality reduction experiments via SLURM, we want to capture the actual plot metadata (categories, label key, cell counts) **at the time of job execution** rather than trying to extract it later. This ensures consistency and traceability.

## How label_key is Determined

### Auto-Detection During Config Generation

The config generator (`scripts/pipeline/config_generator.py`) automatically detects the best `label_key` for each H5AD file by inspecting its `obs` columns. The priority order follows recommended attributes:

1. **Condition:** `disease`, `health_status`, `condition`, `COVID_status`, `disease_status`
   - Distinguishes between diseased vs healthy, treatment status

2. **Stages/Perturbations:** `development_stage`, `disease_stage`, `treatment`, `perturbation`, `lineage`
   - Developmental stages, disease progression, treatment groups

3. **Cell Type:** `cell_type`, `celltype`, `author_cell_type`, `major_celltype`
   - Identity of cell types in the dataset

4. **Longitudinal Time:** `Day`, `timepoint`, `days`, `time`, `visit`
   - Time points in longitudinal studies

5. **Clusters/Annotations:** `cluster`, `leiden`, `annotation`, `region`
   - Fallback clustering or spatial annotations

This auto-detection happens when you run:
```bash
python scripts/run_algorithm.py phate generate-configs
```

Each generated config will have an explicit `label_key` value (e.g., `label_key: development_stage`).

### During SLURM Job Execution

The SLURM post-processing script:
1. Reads the Hydra config from the experiment output (`.hydra/config.yaml`)
2. Extracts the `adata_path` and `label_key` that were used
3. Loads the h5ad file and extracts:
   - Label key name
   - All category values
   - Category counts
   - Number of cells and genes
4. Saves to `plot_metadata.json` alongside experiment outputs

## Changes Made

### 1. Updated Config Generator with Auto-Detection

**File:** `scripts/pipeline/config_generator.py`

Added `auto_detect_label_key()` function that:
- Opens each H5AD file using h5py
- Scans `obs` columns for known metadata columns
- Returns the best matching column with 2-100 categories

### 2. Updated SLURM Job Template

**File:** `scripts/algorithms/phate/slurm_job.slurm`

Added post-processing step that runs immediately after ManyLatents completes.

### 3. Created Post-Processing Module

**File:** `scripts/pipeline/post_process.py`

Utilities for:
- Extracting metadata from a single h5ad file
- Collecting metadata from all experiment outputs
- Regenerating `label_categories.json` from actual outputs

### 4. Created Collection Script

**File:** `scripts/collect_plot_metadata.py`

After SLURM jobs complete, run this to:
- Scan all experiment output directories
- Read `plot_metadata.json` files
- Create consolidated `label_categories.json` mapped by WandB run ID

## Usage

### Running SLURM Jobs with Metadata Extraction

```bash
# Generate the SLURM script
python scripts/run_algorithm.py phate generate-slurm --n-jobs 100 \
    --output slurm_jobs/run_phate_with_metadata.slurm

# Submit to SLURM
sbatch slurm_jobs/run_phate_with_metadata.slurm
```

### After Jobs Complete - Collect Metadata

```bash
# Collect all plot_metadata.json into label_categories.json
python scripts/collect_plot_metadata.py \
    --manylatents-output /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs \
    --wandb-metadata wandb_gallery_replit/wandb_metadata.json \
    --output wandb_gallery_replit/label_categories.json
```

## Output Files

### Per-Experiment: `plot_metadata.json`

Each experiment directory will contain:
```json
{
  "label_key": "development_stage",
  "categories": ["19-year-old stage", "24-year-old stage", ...],
  "num_categories": 29,
  "category_counts": {"19-year-old stage": 3172, "24-year-old stage": 721, ...},
  "n_cells": 50000,
  "n_genes": 14323,
  "adata_file": "A__Balanced__Bone_Marrow_Reference_Map_of_Hematopo_0c4e72a.h5ad"
}
```

### Consolidated: `label_categories.json`

Mapped by WandB run ID:
```json
{
  "hgftnuic": {
    "label_key": "development_stage",
    "categories": ["19-year-old stage", ...],
    "num_categories": 29,
    "dataset_name": "phate_A",
    "source": "manylatents_output",
    ...
  }
}
```

## Benefits

1. **Consistency**: Metadata captured at job execution time
2. **Traceability**: Each experiment has its own metadata snapshot
3. **Reproducibility**: No confusion about which categories were used
4. **Automation**: Fully automated, no manual extraction needed

## Troubleshooting

If post-processing fails, check:
1. `anndata` is installed in the ManyLatents venv
2. `omegaconf` is installed (comes with Hydra)
3. h5ad file paths are correct (scratch → shared mapping)
