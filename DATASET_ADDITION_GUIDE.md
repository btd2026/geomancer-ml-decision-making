# 📊 Adding New Datasets to PHATE Gallery

This guide explains how to add new datasets to the PHATE Gallery with live collaboration.

## 🔄 Quick Update (Automated)

**Option 1: Manual Script**
```bash
# Run the deployment script
./scripts/deploy_gallery.sh
```

**Option 2: GitHub Action**
1. Go to: https://github.com/btd2026/geomancer-ml-decision-making/actions
2. Click "Update PHATE Gallery"
3. Click "Run workflow"

## 📋 Dataset Requirements

Each new dataset needs to be processed and placed in the PHATE results directory:

### Directory Structure
```
/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/
├── Your_New_Dataset/
│   └── runs/
│       ├── default_20260315_120000/
│       │   ├── metadata.json          # ← Required
│       │   ├── colors.json            # ← Required
│       │   ├── dse_metrics.json       # ← Required for DSE display
│       │   ├── config.json            # ← Optional
│       │   └── your_dataset_phate.png # ← Required visualization
│       └── xlarge_20260315_130000/    # ← Additional runs (optional)
│           └── ...
```

### Required Files

**1. `metadata.json` - Dataset Information**
```json
{
  "name": "Your_Dataset_Name",
  "description": "Single-cell RNA-seq analysis of ...",
  "n_obs": 50000,        // Number of cells
  "n_vars": 25000,       // Number of genes
  "h5ad_path": "/path/to/your/dataset.h5ad",
  "label_key": "cell_type",
  "algorithm_type": "phate"
}
```

**2. `colors.json` - Cell Type Color Mapping**
```json
{
  "label_key": "cell_type",
  "n_categories": 8,
  "colors": {
    "T cells": "#1f77b4",
    "B cells": "#ff7f0e",
    "NK cells": "#2ca02c",
    "Monocytes": "#d62728",
    "Dendritic cells": "#9467bd",
    "Neutrophils": "#8c564b",
    "Macrophages": "#e377c2",
    "Other": "#7f7f7f"
  }
}
```

**3. `dse_metrics.json` - DSE Analysis Results**
```json
{
  "name": "Your_Dataset_Name__default_20260315_120000",
  "status": "success",
  "dse_entropy": 8.45,      // Main DSE entropy value
  "dse_count_t10": 1200,    // DSE counts at different thresholds
  "dse_count_t50": 450,
  "dse_count_t100": 280,
  "dse_count_t200": 150,
  "dse_count_t500": 65,
  "algorithm_type": "dse",
  "dse_params": {
    "kernel": "knn",
    "k": 15,
    "alpha": 1.0
  }
}
```

**4. PHATE Visualization Image**
- Filename: `*phate*.png` (any PNG with "phate" in the name)
- Recommended size: 600x456 pixels (4:3 aspect ratio)
- Format: PNG with transparent or white background
- Content: PHATE scatter plot with cell type colors

## 🚀 Manual Addition Process

If you need to add datasets manually:

### Step 1: Generate Gallery Data
```bash
cd scripts/gallery/
python generate_gallery_data.py \
  --phate-results-dir /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/ \
  --output-dir ../../gallery/deployed/ \
  --copy-images \
  --verbose
```

### Step 2: Deploy to Website
```bash
# Copy data and images to docs (GitHub Pages)
cp gallery/deployed/gallery_data_new.json docs/gallery_data.json
cp -r gallery/deployed/images/* docs/images/

# Commit and push
git add docs/gallery_data.json docs/images/
git commit -m "Add new datasets: [list dataset names]

- Dataset A: X cells, Y genes
- Dataset B: X cells, Y genes

Total: Z datasets, W runs"

git push
```

### Step 3: Verify Deployment
1. Wait 2-3 minutes for GitHub Pages to rebuild
2. Check: https://btd2026.github.io/geomancer-ml-decision-making/gallery.html
3. Verify new datasets appear with:
   - ✅ Full PHATE visualization visible
   - ✅ DSE metrics displayed
   - ✅ Color legend expandable
   - ✅ Metadata pills (algorithm, cell count, categories)
   - ✅ Live collaboration working

## 🔍 Troubleshooting

**Dataset not appearing?**
- Check that all required JSON files exist
- Ensure PNG image exists with "phate" in filename
- Run script with `--verbose` flag to see detailed output

**Images not loading?**
- Check image file format (must be PNG)
- Verify image path in generated gallery_data.json
- Ensure images copied to docs/images/ directory

**DSE metrics not showing?**
- Check dse_metrics.json exists and has valid format
- Verify dse_entropy field is present
- Check console for JSON parsing errors

**Color legend empty?**
- Verify colors.json has "colors" object with cell type mappings
- Check that color values are valid hex codes (#rrggbb)
- Ensure categories list matches color keys

## 📈 Current Statistics

The gallery currently contains:
- **91 datasets**
- **292 runs**
- **All PHATE algorithm**
- **12 different label keys** (cell_type, leiden, etc.)

## 🤝 Live Collaboration Features

New datasets automatically support:
- ✅ **Real-time label sharing** across browser tabs
- ✅ **Automatic UI updates** when collaborators make changes
- ✅ **Progress tracking** for multi-run datasets
- ✅ **Export/import** for backup and sharing
- ✅ **Research notes** and quality annotations

Your new datasets will inherit all the modern collaborative features!
