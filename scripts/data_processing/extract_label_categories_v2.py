#!/usr/bin/env python3
"""
Extract actual label category names from h5ad files - IMPROVED VERSION.

This script reads h5ad files and extracts the actual category names
from the obs column that was used for coloring PHATE plots.
Output: JSON file mapping dataset_id -> list of actual category names.

Improvements:
- Uses adata_path from wandb metadata instead of guessing filenames
- Fixes path mappings (scratch -> shared)
- Processes in batches to avoid memory issues
- Better error handling and reporting
"""

import argparse
import json
import sys
from pathlib import Path
import gc

# Add anndata to path
sys.path.insert(0, '/home/btd8/.conda/envs/claude-env/lib/python3.11/site-packages')

try:
    import anndata as ad
    import h5py
except ImportError as e:
    print(f"Error: {e}")
    print("Installing required packages...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'anndata', 'h5py', '-q'])
    import anndata as ad
    import h5py


def fix_adata_path(original_path: str) -> Path:
    """
    Fix the adata_path from wandb metadata to point to actual file location.

    Handles:
    - scratch -> shared directory mapping
    - Removing hash suffixes from filenames
    - Checking both subsampled and processed directories
    """
    # Replace scratch with shared
    path = original_path.replace('/nfs/roberts/scratch/pi_sk2433/btd8/',
                               '/nfs/roberts/project/pi_sk2433/shared/')

    # Try original path first
    adata_path = Path(path)
    if adata_path.exists():
        return adata_path

    # If path contains subsampled but file might be in processed
    if 'subsampled' in path:
        processed_path = path.replace('/subsampled/', '/processed/')
        if Path(processed_path).exists():
            return Path(processed_path)

    # If path contains splits, try removing that part
    if '/subsampled_splits/' in path:
        # Try both subsampled and processed
        for base_dir in ['subsampled', 'processed']:
            # Remove the splits/ part and reconstruct
            parts = path.split('/subsampled_splits/')
            if len(parts) > 1:
                # Get the filename after splits/
                filename = parts[1].split('/')[-1]
                # Try to find matching file in base directories
                for search_dir in ['/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/subsampled/',
                                   '/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/processed/']:
                    for h5ad_file in Path(search_dir).glob('*.h5ad'):
                        # Match by the identifier before __ (the study/dataset ID)
                        file_stem = h5ad_file.stem
                        if filename.split('__')[0] in file_stem or file_stem.startswith(filename.split('__')[0].split('_')[0]):
                            return h5ad_file

    # Try removing the hash suffix (filename__hash.h5ad -> filename.h5ad)
    parts = path.rsplit('__', 1)
    if len(parts) > 1 and parts[0].endswith('.h5ad'):
        # Already has .h5ad before __, so: filename.h5ad__hash -> filename.h5ad
        pass
    elif len(parts) > 1:
        # filename__hash.h5ad -> filename.h5ad
        alt_path = parts[0] + '.h5ad'
        if Path(alt_path).exists():
            return Path(alt_path)

    return None


def extract_label_categories(h5ad_path: Path, label_key: str, max_categories: int = 100) -> list:
    """
    Extract unique category values from h5ad file for a given label_key.
    """
    try:
        adata = ad.read_h5ad(h5ad_path)

        # Check if label_key exists in obs
        if label_key not in adata.obs:
            return None

        # Get unique values - use categorical categories if available
        if hasattr(adata.obs[label_key], 'cat'):
            categories = adata.obs[label_key].cat.categories.tolist()
        else:
            categories = adata.obs[label_key].unique().tolist()

        # Convert to strings and filter out NaN/None
        result = []
        for cat in categories:
            cat_str = str(cat)
            if cat_str not in ['nan', 'None', 'NA', '<NA>', 'nan']:
                result.append(cat_str)

        # Limit to max_categories for sanity
        if len(result) > max_categories:
            result = result[:max_categories]

        # Clean up memory
        del adata
        gc.collect()

        return result

    except Exception as e:
        print(f"    Error processing {h5ad_path.name}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Extract label categories from h5ad files')
    parser.add_argument('--wandb-metadata', type=str,
                        default='wandb_gallery_replit/wandb_metadata.json',
                        help='Path to W&B metadata JSON file')
    parser.add_argument('--output', type=str,
                        default='wandb_gallery_replit/label_categories.json',
                        help='Output JSON file with label categories')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='Number of files to process before saving (default: 10)')
    parser.add_argument('--max-categories', type=int, default=100,
                        help='Maximum categories per dataset (default: 100)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from existing output file')

    args = parser.parse_args()

    # Load W&B metadata
    print(f"Loading W&B metadata from {args.wandb_metadata}...")
    with open(args.wandb_metadata, 'r') as f:
        wandb_metadata = json.load(f)

    print(f"  Found {len(wandb_metadata)} runs")

    # Load existing results if resuming
    results = {}
    if args.resume:
        try:
            with open(args.output, 'r') as f:
                results = json.load(f)
            print(f"  Resuming with {len(results)} existing entries")
        except FileNotFoundError:
            print("  No existing file found, starting fresh")

    # Process each run
    processed = 0
    skipped = 0
    failed = []
    batch_count = 0

    for run_id, run_info in wandb_metadata.items():
        # Skip if already processed
        if run_id in results:
            skipped += 1
            continue

        # Get config data
        config = run_info.get('config', {})
        data_config = config.get('data', {}).get('value', {})

        adata_path_str = data_config.get('adata_path', '')
        label_key = data_config.get('label_key', '')

        if not adata_path_str:
            print(f"{run_id}: No adata_path in config")
            failed.append(run_id)
            continue

        if not label_key:
            print(f"{run_id}: No label_key in config")
            failed.append(run_id)
            continue

        # Fix and find the actual h5ad file
        adata_path = fix_adata_path(adata_path_str)

        if adata_path is None or not adata_path.exists():
            print(f"{run_id}: File not found (tried: {adata_path_str})")
            failed.append(run_id)
            continue

        # Extract categories
        categories = extract_label_categories(adata_path, label_key, args.max_categories)

        if categories:
            results[run_id] = {
                'label_key': label_key,
                'categories': categories,
                'num_categories': len(categories),
                'dataset_name': run_info.get('dataset_name', 'Unknown'),
                'h5ad_file': adata_path.name
            }
            print(f"{run_id}: {label_key} -> {len(categories)} categories")
            processed += 1
            batch_count += 1
        else:
            print(f"{run_id}: Could not extract categories")
            failed.append(run_id)

        # Save periodically
        if batch_count >= args.batch_size:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint: {len(results)} runs saved]")
            batch_count = 0

    # Final save
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total runs: {len(wandb_metadata)}")
    print(f"Processed: {processed}")
    print(f"Skipped (already done): {skipped}")
    print(f"Failed: {len(failed)}")
    print(f"\nOutput saved to: {args.output}")

    if failed:
        print(f"\nFailed runs:")
        for run_id in failed[:10]:
            print(f"  - {run_id}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")


if __name__ == "__main__":
    main()
