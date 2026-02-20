#!/usr/bin/env python3
"""
Interactive browser for CELLxGENE Census datasets.

Search, filter, and export datasets for download to the shared Geomancer folder.

Usage:
    # Browse all datasets with interactive filtering
    python scripts/data_collection/browse_cellxgene_census.py

    # Filter by tissue
    python scripts/data_collection/browse_cellxgene_census.py --tissue "brain"

    # Filter by assay
    python scripts/data_collection/browse_cellxgene_census.py --assay "10x 3' v3"

    # Export top N datasets to CSV for download
    python scripts/data_collection/browse_cellxgene_census.py --export --top 50

    # Search by collection name
    python scripts/data_collection/browse_cellxgene_census.py --search "Tabula"
"""

import cellxgene_census
import pandas as pd
import argparse
from pathlib import Path

# Paths
OUTPUT_DIR = Path('/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data')
METADATA_DIR = Path('data')
EXPORT_FILE = METADATA_DIR / 'datasets_to_download.csv'


def load_datasets(census_version="2025-01-30"):
    """Load all datasets from CELLxGENE Census."""
    print(f"Opening CELLxGENE Census (version {census_version})...")

    with cellxgene_census.open_soma(census_version=census_version) as census:
        # Get dataset metadata
        datasets = census["census_info"]["datasets"].read().concat().to_pandas()
        print(f"Loaded {len(datasets)} datasets")

        # Get cell counts from human data
        human = census["census_data"]["homo_sapiens"]
        cells = human.obs.read(column_names=["dataset_id"]).concat().to_pandas()

        # Count cells per dataset
        cell_counts = cells['dataset_id'].value_counts().reset_index()
        cell_counts.columns = ['dataset_id', 'n_cells']

        # Merge with dataset metadata
        datasets = datasets.merge(cell_counts, on='dataset_id', how='left')
        datasets['n_cells'] = datasets['n_cells'].fillna(0).astype(int)

        # Add dataset_version_id (needed for downloads)
        if 'dataset_id' in datasets.columns:
            datasets['dataset_version_id'] = datasets['dataset_id']

    return datasets


def filter_datasets(datasets, tissue=None, assay=None, min_cells=0, max_cells=None,
                    search_term=None, collection=None):
    """Filter datasets based on criteria."""
    df = datasets.copy()

    # Filter by tissue
    if tissue:
        df = df[df['tissue_general'].str.contains(tissue, case=False, na=False)]

    # Filter by assay
    if assay:
        df = df[df['assay'].str.contains(assay, case=False, na=False)]

    # Filter by cell count
    df = df[df['n_cells'] >= min_cells]
    if max_cells:
        df = df[df['n_cells'] <= max_cells]

    # Filter by collection
    if collection:
        df = df[df['collection_name'].str.contains(collection, case=False, na=False)]

    # Search in title/collection
    if search_term:
        mask = (
            df['dataset_title'].str.contains(search_term, case=False, na=False) |
            df['collection_name'].str.contains(search_term, case=False, na=False)
        )
        df = df[mask]

    return df


def display_datasets(datasets, n=20):
    """Display datasets in a readable format."""
    print(f"\n{'='*100}")
    print(f"Showing {min(n, len(datasets))} of {len(datasets)} datasets")
    print(f"{'='*100}")

    for i, (_, row) in enumerate(datasets.head(n).iterrows()):
        print(f"\n[{i+1}] {row['dataset_id']}")
        print(f"    Title: {row['dataset_title'][:70]}...")
        print(f"    Collection: {row.get('collection_name', 'N/A')}")
        print(f"    Tissue: {row.get('tissue_general', 'N/A')}")
        print(f"    Assay: {row.get('assay', 'N/A')}")
        print(f"    Cells: {row['n_cells']:,}")


def export_for_download(datasets, top_n=None, output_file=EXPORT_FILE):
    """Export datasets to CSV for download script."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # Sort by cell count (descending) and take top N
    to_export = datasets.sort_values('n_cells', ascending=False)
    if top_n:
        to_export = to_export.head(top_n)

    # Prepare export columns
    export_df = to_export[[
        'dataset_id',
        'dataset_title',
        'dataset_total_cell_count'
    ]].copy()
    export_df = export_df.rename(columns={'n_cells': 'dataset_total_cell_count'})

    # Ensure the column exists
    if 'dataset_total_cell_count' not in export_df.columns:
        export_df['dataset_total_cell_count'] = to_export['n_cells']

    export_df.to_csv(output_file, index=False)
    print(f"\n{'='*100}")
    print(f"EXPORTED {len(export_df)} datasets to {output_file}")
    print(f"{'='*100}")
    print(f"\nTo download these datasets, run:")
    print(f"  python scripts/data_collection/download_cellxgene_datasets.py")


def show_summary(datasets):
    """Show summary statistics."""
    print(f"\n{'='*100}")
    print("DATASET SUMMARY")
    print(f"{'='*100}")

    print(f"\nTotal datasets: {len(datasets)}")
    print(f"Total cells: {datasets['n_cells'].sum():,}")

    print(f"\nTop 10 collections:")
    print(datasets['collection_name'].value_counts().head(10).to_string())

    print(f"\nTop 10 tissues:")
    print(datasets['tissue_general'].value_counts().head(10).to_string())

    print(f"\nAssay distribution:")
    print(datasets['assay'].value_counts().head(10).to_string())

    print(f"\nCell count distribution:")
    print(f"  Min: {datasets['n_cells'].min():,}")
    print(f"  Max: {datasets['n_cells'].max():,}")
    print(f"  Median: {datasets['n_cells'].median():,.0f}")
    print(f"  Mean: {datasets['n_cells'].mean():,.0f}")


def main():
    parser = argparse.ArgumentParser(
        description='Browse and search CELLxGENE Census datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--tissue', help='Filter by tissue type (e.g., "brain", "blood")')
    parser.add_argument('--assay', help='Filter by assay (e.g., "10x 3\' v3", "Smart-seq2")')
    parser.add_argument('--collection', help='Filter by collection name')
    parser.add_argument('--search', help='Search term in title or collection')
    parser.add_argument('--min-cells', type=int, default=0, help='Minimum cell count')
    parser.add_argument('--max-cells', type=int, help='Maximum cell count')
    parser.add_argument('--top', type=int, help='Show only top N datasets by cell count')
    parser.add_argument('--export', action='store_true', help='Export filtered datasets to CSV for download')
    parser.add_argument('--export-top', type=int, help='Export top N datasets to CSV')
    parser.add_argument('--summary', action='store_true', help='Show summary statistics only')

    args = parser.parse_args()

    # Load datasets
    datasets = load_datasets()

    # Apply filters
    filtered = filter_datasets(
        datasets,
        tissue=args.tissue,
        assay=args.assay,
        min_cells=args.min_cells,
        max_cells=args.max_cells,
        search_term=args.search,
        collection=args.collection
    )

    # Sort by cell count
    filtered = filtered.sort_values('n_cells', ascending=False)

    # Limit to top N if specified
    if args.top:
        filtered = filtered.head(args.top)

    # Show results
    if args.summary:
        show_summary(filtered)
    elif args.export or args.export_top:
        display_datasets(filtered, n=10)
        export_for_download(datasets if args.export_top else filtered,
                           top_n=args.export_top)
    else:
        show_summary(filtered)
        display_datasets(filtered, n=20)


if __name__ == "__main__":
    main()
