#!/usr/bin/env python3
"""
Convenience wrapper for preprocessing data.

This script provides a simple interface to the preprocessing pipeline.
Use this before running any dimensionality reduction experiments.

Usage:
    # Process a directory of files
    python scripts/preprocess.py /path/to/raw_data --output /path/to/processed

    # Process with custom settings
    python scripts/preprocess.py /path/to/raw_data --max-cells 10000

    # Validate existing files
    python scripts/preprocess.py /path/to/data --validate
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.preprocessing import PreprocessingPipeline, PreprocessingConfig


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess data for Geomancer experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process directory (default settings)
  python scripts/preprocess.py /path/to/raw_data -o /path/to/processed

  # Process with subsampling
  python scripts/preprocess.py /path/to/raw_data -o /path/to/processed --max-cells 10000

  # Validate existing files
  python scripts/preprocess.py /path/to/h5ad_files --validate

  # Process CSV files
  python scripts/preprocess.py /path/to/csv_files -o /path/to/h5ad_files --pattern "*.csv"
        """
    )

    parser.add_argument(
        "input_dir",
        type=str,
        help="Input directory with data files"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        help="Output directory for processed H5AD files",
    )
    parser.add_argument(
        "--validate", "--check",
        action="store_true",
        help="Only validate existing H5AD files, don't process"
    )
    parser.add_argument(
        "--pattern", "-p",
        type=str,
        default="*.*",
        help="File pattern to match (default: *.*)"
    )
    parser.add_argument(
        "--max-cells",
        type=int,
        default=50000,
        help="Maximum cells per dataset (default: 50000)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--stratify-by",
        type=str,
        help="Column for stratified subsampling (auto-detected if not specified)"
    )
    parser.add_argument(
        "--report", "-r",
        type=str,
        help="Path to save JSON report"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--min-cells",
        type=int,
        default=100,
        help="Minimum cells required per dataset (default: 100)"
    )
    parser.add_argument(
        "--min-genes",
        type=int,
        default=100,
        help="Minimum genes per cell (default: 100)"
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        sys.exit(1)

    # Create config
    config = PreprocessingConfig(
        max_cells=args.max_cells,
        seed=args.seed,
        min_cells=args.min_cells,
        min_genes=args.min_genes,
    )

    # Validate mode
    if args.validate:
        print(f"Validating files in: {input_dir}")
        print(f"Pattern: {args.pattern}\n")

        import scanpy as sc
        from pipeline.preprocessing import MetadataValidator

        input_files = list(input_dir.glob(args.pattern))
        print(f"Found {len(input_files)} files\n")

        all_valid = True
        for i, fpath in enumerate(input_files, 1):
            print(f"[{i}/{len(input_files)}] {fpath.name}")
            try:
                adata = sc.read_h5ad(fpath)
                is_valid, warnings = MetadataValidator.validate(adata, config)

                print(f"  Cells: {adata.n_obs:,}, Genes: {adata.n_vars:,}")

                if warnings:
                    for warning in warnings[:3]:  # Show first 3 warnings
                        print(f"  {warning}")

                if is_valid:
                    suggested = MetadataValidator.suggest_label_key(adata)
                    if suggested:
                        n_cats = MetadataValidator.count_categories(adata, suggested)
                        print(f"  ✓ Suggested label: {suggested} ({n_cats} categories)")
                    else:
                        print(f"  ⚠ No suitable label key found")
                else:
                    print(f"  ✗ Validation failed")
                    all_valid = False

            except Exception as e:
                print(f"  ✗ Error: {e}")
                all_valid = False

            print()

        if all_valid:
            print("✓ All files validated")
        else:
            print("✗ Some files failed validation")
            sys.exit(1)
        return

    # Processing mode
    if not args.output_dir:
        print("Error: --output-dir required for processing")
        print("Use --validate to only check existing files")
        sys.exit(1)

    output_dir = Path(args.output_dir)

    print("="*60)
    print("GEOMANCER PREPROCESSING PIPELINE")
    print("="*60)
    print(f"Input directory:  {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Pattern:          {args.pattern}")
    print(f"Max cells:        {args.max_cells:,}")
    print(f"Seed:             {args.seed}")
    print("="*60)

    pipeline = PreprocessingPipeline(config)

    reports = pipeline.process_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        pattern=args.pattern,
        skip_existing=not args.force,
        stratify_by=args.stratify_by,
    )

    pipeline.print_summary()

    if args.report:
        pipeline.save_report(Path(args.report))


if __name__ == "__main__":
    main()
