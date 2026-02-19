#!/usr/bin/env python3
"""
Main entry point for running dimensionality reduction algorithms.

This script provides a unified CLI for running any algorithm through the
reorganized pipeline infrastructure.

Examples:
    # List available algorithms
    python scripts/run_algorithm.py --list

    # Generate configs for PHATE
    python scripts/run_algorithm.py phate generate-configs

    # Run PHATE experiments via SLURM
    python scripts/run_algorithm.py phate run --mode slurm

    # Run PHATE experiments locally
    python scripts/run_algorithm.py phate run --mode local

    # Generate SLURM job script
    python scripts/run_algorithm.py phate generate-slurm --n-jobs 100
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from algorithms import get_algorithm, list_algorithms, get_algorithm_names
from pipeline.config_generator import AlgorithmConfigGenerator
from pipeline.slurm_template import SlurmJobGenerator, SlurmResources
from pipeline.experiment_runner import ExperimentRunner


# Default paths (can be overridden via config file or environment)
DEFAULT_DATA_DIR = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/subsampled")
DEFAULT_MANYLATENTS_DIR = Path("/home/btd8/manylatents")
DEFAULT_OUTPUT_BASE = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs")


def cmd_list(args) -> None:
    """List available algorithms."""
    names = get_algorithm_names()
    print("Available algorithms:")
    for key, name in sorted(names.items()):
        config = get_algorithm(key)
        print(f"  {key:12s} - {name}")
        if config.description:
            print(f"               {config.description[:70]}...")
    print(f"\nUse: python {Path(__file__).name} <algorithm> <command>")


def cmd_generate_configs(args) -> None:
    """Generate experiment configs for an algorithm."""
    algorithm = args.algorithm
    config = get_algorithm(algorithm)

    print(f"Generating configs for {config.name}...")

    generator = AlgorithmConfigGenerator(
        algorithm_name=algorithm,
        manylatents_dir=args.manylatents_dir,
        data_dir=args.data_dir,
        output_base=args.output_dir,
    )

    # Use algorithm defaults
    algorithm_params = config.get_default_params()

    # Override with command line args if provided
    if args.n_components is not None:
        algorithm_params['n_components'] = args.n_components
    if args.knn is not None:
        algorithm_params['knn'] = args.knn
    if args.t is not None:
        algorithm_params['t'] = args.t
    if args.decay is not None:
        algorithm_params['decay'] = args.decay

    configs = generator.generate_configs(algorithm_params=algorithm_params)
    print(f"\nGenerated {len(configs)} configs.")


def cmd_generate_slurm(args) -> None:
    """Generate SLURM job script."""
    algorithm = args.algorithm
    config = get_algorithm(algorithm)

    print(f"Generating SLURM script for {config.name}...")

    generator = SlurmJobGenerator(
        algorithm=algorithm,
        manylatents_dir=args.manylatents_dir,
        output_base=args.output_dir,
    )

    # Get resources from config
    resources = SlurmResources.from_dict(config.get_resource_requirements())

    # Override with command line args if provided
    if args.mem:
        resources.mem = args.mem
    if args.cpus:
        resources.cpus = args.cpus
    if args.time:
        resources.time = args.time
    if args.partition:
        resources.partition = args.partition

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("slurm_jobs") / f"run_{algorithm}_array.slurm"

    generator.write_job_script(output_path, args.n_jobs, resources)

    print(f"Generated: {output_path}")
    print(f"  Jobs: {args.n_jobs}")
    print(f"  Resources: {resources.cpus} CPUs, {resources.mem}, {resources.time}")
    print(f"\nTo submit: sbatch {output_path}")


def cmd_run(args) -> None:
    """Run experiments."""
    algorithm = args.algorithm
    config = get_algorithm(algorithm)

    if args.mode == "slurm":
        print(f"SLURM mode: Generate and submit SLURM job script")
        print("Use 'generate-slurm' command first, then 'sbatch' to submit.")
        return

    print(f"Running experiments for {config.name}...")

    runner = ExperimentRunner(
        algorithm=algorithm,
        manylatents_dir=args.manylatents_dir,
        output_base=args.output_dir,
    )

    runner.run(
        parallel=args.parallel,
        start=args.start,
        end=args.end,
        verbose=args.verbose,
        dry_run=args.dry_run,
    )


def cmd_info(args) -> None:
    """Show information about an algorithm."""
    algorithm = args.algorithm
    config = get_algorithm(algorithm)

    print(f"Algorithm: {config.name}")
    print(f"Key: {config.manylatents_key}")
    print(f"Embedding key: {config.embedding_key}")
    print(f"\nDescription:")
    print(f"  {config.description}")
    print(f"\nDefault parameters:")
    for key, value in config.get_default_params().items():
        print(f"  {key}: {value}")
    print(f"\nResource requirements:")
    for key, value in config.get_resource_requirements().items():
        print(f"  {key}: {value}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run dimensionality reduction algorithms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_algorithm.py --list
  python scripts/run_algorithm.py phate generate-configs
  python scripts/run_algorithm.py phate generate-slurm --n-jobs 100
  python scripts/run_algorithm.py phate run --mode local --parallel 4
        """
    )

    # Global arguments
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available algorithms"
    )

    # Algorithm (positional when not using --list)
    parser.add_argument(
        "algorithm",
        nargs="?",
        help="Algorithm name (e.g., phate, umap, tsne)"
    )

    # Command (positional)
    parser.add_argument(
        "command",
        nargs="?",
        choices=["generate-configs", "generate-slurm", "run", "info"],
        help="Command to run"
    )

    # Remaining args will be parsed by sub-command
    args, remaining = parser.parse_known_args()

    # Handle --list
    if args.list:
        cmd_list(args)
        return

    # Validate algorithm
    if not args.algorithm:
        parser.print_help()
        print("\nError: Please specify an algorithm or use --list")
        sys.exit(1)

    try:
        get_algorithm(args.algorithm)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nAvailable algorithms:", ", ".join(list_algorithms()))
        sys.exit(1)

    # Parse command
    if not args.command:
        parser.print_help()
        print("\nError: Please specify a command")
        print("  Available: generate-configs, generate-slurm, run, info")
        sys.exit(1)

    # Create sub-parser for command-specific args
    subparser = argparse.ArgumentParser(add_help=False)

    # Common arguments for all commands
    subparser.add_argument(
        "--manylatents-dir",
        type=str,
        default=str(DEFAULT_MANYLATENTS_DIR),
        help="Path to ManyLatents installation"
    )
    subparser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_BASE),
        help="Output directory"
    )

    # Command-specific arguments
    if args.command == "generate-configs":
        subparser.add_argument(
            "--data-dir",
            type=str,
            default=str(DEFAULT_DATA_DIR),
            help="Directory with H5AD files"
        )
        subparser.add_argument(
            "--n-components",
            type=int,
            help="Number of components"
        )
        subparser.add_argument(
            "--knn",
            type=int,
            help="Number of nearest neighbors (PHATE)"
        )
        subparser.add_argument(
            "--t",
            type=int,
            help="Diffusion time (PHATE)"
        )
        subparser.add_argument(
            "--decay",
            type=int,
            help="Decay rate (PHATE)"
        )

    elif args.command == "generate-slurm":
        subparser.add_argument(
            "--n-jobs",
            type=int,
            required=True,
            help="Number of array jobs"
        )
        subparser.add_argument(
            "--output",
            type=str,
            help="Output script path"
        )
        subparser.add_argument(
            "--mem",
            type=str,
            help="Memory per job"
        )
        subparser.add_argument(
            "--cpus",
            type=int,
            help="CPUs per job"
        )
        subparser.add_argument(
            "--time",
            type=str,
            help="Time limit"
        )
        subparser.add_argument(
            "--partition",
            type=str,
            help="SLURM partition"
        )

    elif args.command == "run":
        subparser.add_argument(
            "--mode",
            type=str,
            choices=["local", "slurm", "dry-run"],
            default="local",
            help="Execution mode"
        )
        subparser.add_argument(
            "--parallel",
            type=int,
            default=1,
            help="Number of parallel processes"
        )
        subparser.add_argument(
            "--start",
            type=int,
            default=0,
            help="Start index"
        )
        subparser.add_argument(
            "--end",
            type=int,
            help="End index"
        )
        subparser.add_argument(
            "--verbose",
            action="store_true",
            help="Verbose output"
        )
        subparser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print without running"
        )

    # Parse remaining args
    cmd_args = subparser.parse_args(remaining)
    cmd_args.algorithm = args.algorithm

    # Execute command
    if args.command == "generate-configs":
        cmd_generate_configs(cmd_args)
    elif args.command == "generate-slurm":
        cmd_generate_slurm(cmd_args)
    elif args.command == "run":
        cmd_run(cmd_args)
    elif args.command == "info":
        cmd_info(cmd_args)


if __name__ == "__main__":
    main()
