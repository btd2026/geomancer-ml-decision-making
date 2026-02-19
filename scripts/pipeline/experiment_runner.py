#!/usr/bin/env python3
"""
Generic experiment runner for ManyLatents experiments.

This script runs ManyLatents experiments either sequentially or in parallel,
supporting any algorithm.
"""

import subprocess
import yaml
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import sys
from typing import Optional, List, Dict, Any, Tuple


class ExperimentRunner:
    """Run ManyLatents experiments for any algorithm."""

    def __init__(
        self,
        algorithm: str,
        manylatents_dir: Path,
        output_base: Path,
    ):
        """
        Initialize the experiment runner.

        Args:
            algorithm: Algorithm name (e.g., "phate", "umap")
            manylatents_dir: Path to ManyLatents installation
            output_base: Base directory for experiment outputs
        """
        self.algorithm = algorithm.lower()
        self.manylatents_dir = Path(manylatents_dir)
        self.output_base = Path(output_base)
        self.experiment_list = self.manylatents_dir / f"{self.algorithm}_experiments.yaml"

    def run_experiment(
        self,
        exp_name: str,
        verbose: bool = False,
        timeout: int = 3600,
    ) -> Tuple[str, str, Optional[str]]:
        """
        Run a single experiment.

        Args:
            exp_name: Experiment name
            verbose: Print detailed output
            timeout: Timeout in seconds (default: 1 hour)

        Returns:
            Tuple of (exp_name, status, error_message)
            Status is one of: "success", "failed", "timeout", "error"
        """
        cmd = [
            "python3", "-m", "manylatents.main",
            f"experiment=cellxgene/{exp_name}",
            "logger=none",
            f"hydra.run.dir={self.output_base}/{exp_name}"
        ]

        if verbose:
            print(f"\n{'='*60}")
            print(f"Running: {exp_name}")
            print(f"Command: {' '.join(cmd)}")
            print(f"{'='*60}\n")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.manylatents_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                if verbose:
                    print(f"Completed: {exp_name}")
                return exp_name, "success", None
            else:
                error_msg = f"Exit code {result.returncode}"
                if verbose:
                    print(f"Failed: {exp_name} - {error_msg}")
                    print(f"stderr: {result.stderr[-500:]}")
                return exp_name, "failed", error_msg

        except subprocess.TimeoutExpired:
            if verbose:
                print(f"Timeout: {exp_name}")
            return exp_name, "timeout", f"Experiment timed out after {timeout} seconds"
        except Exception as e:
            if verbose:
                print(f"Error: {exp_name} - {str(e)}")
            return exp_name, "error", str(e)

    def load_experiments(self) -> List[Dict[str, Any]]:
        """
        Load experiment list from YAML file.

        Returns:
            List of experiment dictionaries
        """
        if not self.experiment_list.exists():
            raise FileNotFoundError(
                f"Experiment list not found: {self.experiment_list}\n"
                f"Run config generation first!"
            )

        with open(self.experiment_list, 'r') as f:
            data = yaml.safe_load(f)
            return data['experiments']

    def run(
        self,
        parallel: int = 1,
        start: int = 0,
        end: Optional[int] = None,
        verbose: bool = False,
        dry_run: bool = False,
        timeout: int = 3600,
    ) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        """
        Run experiments.

        Args:
            parallel: Number of parallel processes (1 for sequential)
            start: Start index (inclusive)
            end: End index (exclusive)
            verbose: Print detailed progress
            dry_run: Print experiments without running
            timeout: Per-experiment timeout in seconds

        Returns:
            Dictionary with status -> list of (name, error) tuples
        """
        # Load experiments
        experiments = self.load_experiments()

        # Select subset
        end = end if end is not None else len(experiments)
        experiments = experiments[start:end]

        print(f"Algorithm: {self.algorithm}")
        print(f"Total experiments: {len(experiments)}")
        print(f"Parallel workers: {parallel}")
        print(f"Output directory: {self.output_base}")

        if dry_run:
            print("\nExperiments to run:")
            for i, exp in enumerate(experiments, start=start):
                print(f"  {i:3d}. {exp['name']}")
            return {}

        # Create output directory
        self.output_base.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        results = {"success": [], "failed": [], "timeout": [], "error": []}

        # Run experiments
        if parallel == 1:
            # Sequential execution
            for i, exp in enumerate(experiments, start=start):
                print(f"\n[{i+1}/{len(experiments)}] Running: {exp['name']}")
                name, status, error = self.run_experiment(exp['name'], verbose, timeout)
                results[status].append((name, error))
        else:
            # Parallel execution
            print(f"\nRunning {len(experiments)} experiments with {parallel} workers...")
            with ProcessPoolExecutor(max_workers=parallel) as executor:
                futures = {
                    executor.submit(self.run_experiment, exp['name'], verbose, timeout): exp
                    for exp in experiments
                }

                for i, future in enumerate(as_completed(futures), 1):
                    exp = futures[future]
                    name, status, error = future.result()
                    results[status].append((name, error))
                    print(f"[{i}/{len(experiments)}] {status.upper()}: {name}")

        # Print summary
        elapsed = time.time() - start_time
        self._print_summary(elapsed, results)

        # Save results
        self._save_results(results)

        return results

    def _print_summary(
        self,
        elapsed: float,
        results: Dict[str, List[Tuple[str, Optional[str]]]],
    ) -> None:
        """Print execution summary."""
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total time: {elapsed/60:.1f} minutes")
        print(f"Success: {len(results['success'])}")
        print(f"Failed:  {len(results['failed'])}")
        print(f"Timeout: {len(results['timeout'])}")
        print(f"Errors:  {len(results['error'])}")

        if results['failed'] or results['timeout'] or results['error']:
            print(f"\n{'='*60}")
            print("FAILURES")
            print(f"{'='*60}")
            for status in ['failed', 'timeout', 'error']:
                if results[status]:
                    print(f"\n{status.upper()}:")
                    for name, error in results[status]:
                        print(f"  - {name}: {error}")

    def _save_results(
        self,
        results: Dict[str, List[Tuple[str, Optional[str]]]],
    ) -> None:
        """Save results to YAML file."""
        results_file = self.output_base / f"{self.algorithm}_run_results.yaml"
        with open(results_file, 'w') as f:
            yaml.dump(results, f)
        print(f"\nResults saved to: {results_file}")


def main():
    """CLI entry point for experiment running."""
    import argparse

    DEFAULT_MANYLATENTS_DIR = Path("/home/btd8/manylatents")
    DEFAULT_OUTPUT_BASE = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs")

    parser = argparse.ArgumentParser(
        description="Run ManyLatents experiments for any algorithm"
    )
    parser.add_argument(
        "algorithm",
        type=str,
        help="Algorithm name (e.g., phate, umap, tsne)"
    )
    parser.add_argument(
        "--manylatents-dir",
        type=str,
        default=str(DEFAULT_MANYLATENTS_DIR),
        help=f"Path to ManyLatents (default: {DEFAULT_MANYLATENTS_DIR})"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_BASE),
        help=f"Output directory (default: {DEFAULT_OUTPUT_BASE})"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel processes (default: 1)"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index (default: 0)"
    )
    parser.add_argument(
        "--end",
        type=int,
        help="End index (exclusive)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print experiments without running"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Per-experiment timeout in seconds (default: 3600)"
    )

    args = parser.parse_args()

    # Create runner and run
    runner = ExperimentRunner(
        algorithm=args.algorithm,
        manylatents_dir=Path(args.manylatents_dir),
        output_base=Path(args.output_dir),
    )

    runner.run(
        parallel=args.parallel,
        start=args.start,
        end=args.end,
        verbose=args.verbose,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
