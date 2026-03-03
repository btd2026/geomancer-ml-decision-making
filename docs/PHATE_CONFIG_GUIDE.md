# PHATE Configuration Guide

This guide explains how to configure and run PHATE embedding experiments using the ManyLatents + Hydra Submitit pipeline.

## Quick Start

1. Edit `configs/phate_experiments.yaml` with your experiments
2. Run `python scripts/phate/run_phate.py configs/phate_experiments.yaml --preview` to verify
3. Run `python scripts/phate/run_phate.py configs/phate_experiments.yaml --submit` to submit jobs

## Configuration File

The main configuration file is `configs/phate_experiments.yaml`. Here's a complete example:

```yaml
# Base directory for H5AD files (all h5ad_file paths are relative to this)
h5ad_base_dir: "/path/to/h5ad/files"

# ManyLatents installation directory
manylatents_dir: "/home/btd8/manylatents"

# Cluster config to use (yale, mila, narval, etc.)
cluster: "yale"

# Output directory for results
output_dir: "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs"

# Default PHATE parameters (applied to all experiments unless overridden)
defaults:
  phate:
    n_components: 2
    knn: 100
    t: 12
    decay: 60
    seed: 42

  # Label key: "auto" for automatic detection, or specify column name
  label_key: "auto"

  # SLURM resource preset: small, medium, or large
  slurm_preset: "medium"

  # Output options
  output:
    generate_plot: true
    save_embedding: true
    compute_metrics: true
    extract_metadata: true

# Experiments list
experiments:
  - name: "my_dataset"
    h5ad_file: "my_dataset.h5ad"  # Relative to h5ad_base_dir

  - name: "another_experiment"
    h5ad_file: "subfolder/dataset2.h5ad"
    phate: { knn: 150 }  # Override specific PHATE params
```

## SLURM Resource Presets

| Preset | mem_gb | cpus | timeout_min | Partition | Best For |
|--------|--------|------|-------------|-----------|----------|
| small | 16 | 2 | 60 | day | Datasets < 50k cells |
| medium | 32 | 4 | 240 | day | Datasets 50k-200k cells |
| large | 64 | 8 | 480 | day | Datasets 200k-1M cells |
| bigmem | 128 | 16 | 480 | bigmem | Very large datasets |

## Command-Line Interface

### Preview Mode

Detect label keys and show dataset info without generating files:

```bash
python scripts/phate/run_phate.py configs/phate_experiments.yaml --preview
```

Output example:
```
=========================== Experiment: my_dataset ===========================
H5AD: /path/to/h5ad/files/my_dataset.h5ad
  Label key: auto
  Detected label key: cell_type
  Categories: 15
  Top categories:
    - T cells: 5234 cells
    - B cells: 3421 cells
    ...
  PHATE params: knn=100, t=12, decay=60
```

### Generate Configs Only

Generate ManyLatents YAML files without submitting:

```bash
python scripts/phate/run_phate.py configs/phate_experiments.yaml --generate-configs
```

Configs are generated to: `/home/btd8/manylatents/manylatents/configs/experiment/custom/`

### Submit to SLURM

Generate configs and submit via Hydra Submitit:

```bash
python scripts/phate/run_phate.py configs/phate_experiments.yaml --submit
```

### Local Testing

Run a single experiment locally (for debugging):

```bash
python scripts/phate/run_phate.py configs/phate_experiments.yaml --local --experiment my_dataset
```

### Dry Run

See what command would be executed without running:

```bash
python scripts/phate/run_phate.py configs/phate_experiments.yaml --submit --dry-run
```

## Label Key Detection

The system automatically detects suitable label columns. Priority order:

1. User-specified `label_key` in experiment config
2. Default `label_key` from defaults section
3. Auto-detection from common names: `cell_type`, `cluster`, `leiden`, `louvain`, etc.
4. First categorical column with 2-500 unique values

To specify a label key:

```yaml
experiments:
  - name: "my_dataset"
    h5ad_file: "my_dataset.h5ad"
    label_key: "cell_type_ontology_term_id"
```

## PHATE Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| n_components | 2 | Output dimensionality |
| knn | 100 | Number of nearest neighbors |
| t | 12 | Time scale for diffusion |
| decay | 60 | Decay rate for kernel |
| seed | 42 | Random seed |

Override per experiment:

```yaml
experiments:
  - name: "large_dataset"
    h5ad_file: "large.h5ad"
    phate:
      knn: 150  # More neighbors for large datasets
      t: 15     # Longer diffusion time
```

## Output Structure

Results are saved to:

```
output_dir/
  experiment_name/
    metadata.json           # All metadata combined
    dataset_metadata.json   # Dataset statistics
    embedding_metrics.json  # Embedding quality metrics
    quality_metrics.json    # Neighborhood preservation, silhouette
    embedding.csv           # PHATE coordinates (if save_embedding: true)
```

## Metadata Fields

### Dataset Metadata
- `n_obs`: Number of cells
- `n_vars`: Number of genes
- `label_key`: Column used for labels
- `n_categories`: Number of unique labels
- `categories`: List of category names and counts

### Embedding Metrics
- `shape`: Embedding dimensions
- `dim_N_stats`: Per-dimension statistics (min, max, mean, std)
- `pairwise_distance_stats`: Distance distribution

### Quality Metrics
- `neighborhood_preservation_kN`: KNN preservation at k=5, 10, 15
- `silhouette_score`: Label separation quality

## Workflow Summary

```
1. Edit configs/phate_experiments.yaml
   ↓
2. Run: python scripts/phate/run_phate.py --preview
   ↓ (verify label detection)
3. Run: python scripts/phate/run_phate.py --submit
   ↓
4. ManyLatents configs generated
   ↓
5. Hydra MULTIRUN with Submitit launcher
   ↓
6. SLURM array job submitted
   ↓
7. Monitor: squeue -u $USER
   ↓
8. Results in output_dir/
```

## Troubleshooting

### H5AD file not found

Check that `h5ad_base_dir` is correct and paths are relative to it.

### No suitable label key detected

The auto-detection couldn't find a good column. Either:
- Specify `label_key` explicitly
- Check available columns with `--preview`

### SLURM job fails

Check:
- Partition exists (`sinfo`)
- Resource limits are sufficient
- Environment modules loaded in cluster config

### Memory issues

Use a larger SLURM preset or customize resources:

```yaml
experiments:
  - name: "big_data"
    h5ad_file: "big.h5ad"
    slurm_preset: "bigmem"
```

## Advanced: Direct ManyLatents Usage

If you prefer to create ManyLatents configs manually:

```bash
cd /home/btd8/manylatents
python -m manylatents.main experiment=custom/phate_my_dataset cluster=yale
```

The generated configs follow ManyLatents' standard format with:
- `algorithms.latent.*`: PHATE parameters
- `data.adata_path`: Path to H5AD file
- `data._metadata_.label_key`: Label column name
