#!/usr/bin/env python3
"""
Automatic OOM failure detection and resubmission.

This script scans SLURM logs for OOM failures and resubmits failed jobs
with escalated resources.

Usage:
    # Check for OOM failures
    python scripts/utils/resubmit_oom.py --check

    # Resubmit failed jobs with escalated resources
    python scripts/utils/resubmit_oom.py --resubmit

    # Dry run to see what would be resubmitted
    python scripts/utils/resubmit_oom.py --resubmit --dry-run
"""

import argparse
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from resource_config import (
    ResourcePreset,
    get_config,
    escalate_preset,
    get_resource_preset,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class OOMFailure:
    """Represents an OOM failure from SLURM logs."""
    job_id: str
    array_task_id: Optional[str]
    dataset_name: str
    log_file: Path
    current_preset: ResourcePreset


def detect_oom_failures(log_dir: Path, pattern: str = "*.err") -> list[OOMFailure]:
    """
    Scan log files for OOM failures.

    Args:
        log_dir: Directory containing SLURM log files
        pattern: Glob pattern for error logs

    Returns:
        List of OOMFailure objects
    """
    failures = []

    for log_file in sorted(log_dir.glob(pattern)):
        content = log_file.read_text()

        # Check for OOM kill indicator
        if "oom_kill" not in content.lower():
            continue

        # Extract job ID from filename (e.g., phate_replot_136.err -> 136)
        match = re.search(r'(\d+)(?:_\d+)?\.err$', log_file.name)
        if not match:
            continue
        job_id = match.group(1)

        # Extract dataset name from log content
        dataset_match = re.search(r'\[1/\d+\]\s+(.+?)\s*$', content, re.MULTILINE)
        if not dataset_match:
            continue
        dataset_name = dataset_match.group(1).strip()

        # Try to determine current preset from log or use default
        current_preset = ResourcePreset.SMALL  # Default assumption
        if "256G" in content or "xlarge" in content.lower():
            current_preset = ResourcePreset.XLARGE
        elif "128G" in content or "large" in content.lower():
            current_preset = ResourcePreset.LARGE
        elif "64G" in content or "medium" in content.lower():
            current_preset = ResourcePreset.MEDIUM

        failures.append(OOMFailure(
            job_id=job_id,
            array_task_id=None,
            dataset_name=dataset_name,
            log_file=log_file,
            current_preset=current_preset,
        ))

    return failures


def get_dataset_size(dataset_name: str, results_dir: Path) -> Optional[int]:
    """
    Get the number of cells for a dataset from metadata.

    Args:
        dataset_name: Full dataset run name (e.g., "DatasetName__run_id")
        results_dir: Directory containing PHATE results

    Returns:
        Number of cells, or None if not found
    """
    # Parse dataset name: "DatasetName__run_id" -> "DatasetName"
    parts = dataset_name.split("__")
    if len(parts) < 2:
        return None
    dataset_dir = results_dir / parts[0]

    # Check for dataset metadata
    metadata_file = dataset_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)
            return metadata.get("n_obs")

    # Check run metadata
    runs_dir = dataset_dir / "runs"
    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            run_metadata = run_dir / "metadata.json"
            if run_metadata.exists():
                with open(run_metadata) as f:
                    metadata = json.load(f)
                    # Check if this matches our run
                    if dataset_name.endswith(run_dir.name):
                        return metadata.get("n_cells")

    return None


def generate_resubmission_script(
    failures: list[OOMFailure],
    script_path: Path,
    command_template: str,
    results_dir: Path,
) -> bool:
    """
    Generate a SLURM script to resubmit failed jobs with escalated resources.

    Args:
        failures: List of OOM failures
        script_path: Where to write the SLURM script
        command_template: Template for command (e.g., "python scripts/phate/regenerate.py --dataset {dataset}")
        results_dir: Directory containing results (for size lookup)

    Returns:
        True if script was generated successfully
    """
    if not failures:
        logger.info("No OOM failures to resubmit")
        return False

    # Group failures by escalated preset
    by_preset: dict[ResourcePreset, list[OOMFailure]] = {}
    for failure in failures:
        new_preset = escalate_preset(failure.current_preset)
        if new_preset is None:
            logger.warning(f"Cannot escalate {failure.dataset_name}: already at XLARGE")
            continue
        if new_preset not in by_preset:
            by_preset[new_preset] = []
        by_preset[new_preset].append(failure)

    if not by_preset:
        logger.warning("No failures can be escalated")
        return False

    # Generate script for the largest preset needed (use single script for simplicity)
    max_preset = max(by_preset.keys(), key=lambda p: list(ResourcePreset).index(p))
    config = get_config(max_preset)
    all_failures = failures

    # Escape dataset names for bash
    datasets = [f'"{f.dataset_name}"' for f in all_failures]
    datasets_str = " ".join(datasets)

    script = f"""#!/bin/bash
#SBATCH --job-name=phate_oom_retry
#SBATCH --array=0-{len(all_failures)-1}%{config.max_concurrent}
#SBATCH --mem={config.mem_gb}G
#SBATCH --cpus-per-task={config.cpus}
#SBATCH --time={config.time_hours:02d}:00:00
#SBATCH --partition={config.partition}
#SBATCH --output=logs/phate_oom_retry_%a.out
#SBATCH --error=logs/phate_oom_retry_%a.err

# Auto-generated OOM recovery script
# Original failures escalated to {max_preset.value} resources
# Generated datasets: {len(all_failures)}

source /home/btd8/manylatents/.venv/bin/activate

DATASETS=({datasets_str})
DATASET_NAME=${{DATASETS[$SLURM_ARRAY_TASK_ID]}}

{command_template.format(dataset="$DATASET_NAME")}
"""

    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w") as f:
        f.write(script)

    logger.info(f"Generated resubmission script: {script_path}")
    logger.info(f"  Jobs: {len(all_failures)}")
    logger.info(f"  Preset: {max_preset.value} ({config.mem_gb}GB, {config.time_hours}hr)")
    logger.info(f"\nTo submit: sbatch {script_path}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Detect and resubmit OOM-failed jobs")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"),
                        help="Directory containing SLURM logs")
    parser.add_argument("--pattern", default="phate_replot*.err",
                        help="Glob pattern for error logs")
    parser.add_argument("--results-dir", type=Path,
                        default=Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results"),
                        help="Directory containing PHATE results")
    parser.add_argument("--check", action="store_true",
                        help="Check for OOM failures without resubmitting")
    parser.add_argument("--resubmit", action="store_true",
                        help="Generate resubmission script for failed jobs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without writing files")
    parser.add_argument("--command", default="python scripts/phate/regenerate_hierarchical_plots.py --run --dataset {dataset}",
                        help="Command template for resubmission")
    parser.add_argument("--output-script", type=Path, default=Path("slurm_jobs/oom_retry.slurm"),
                        help="Where to write resubmission script")

    args = parser.parse_args()

    # Detect failures
    failures = detect_oom_failures(args.log_dir, args.pattern)

    if not failures:
        logger.info("No OOM failures detected")
        return

    logger.info(f"Found {len(failures)} OOM failures:")
    for f in failures:
        size = get_dataset_size(f.dataset_name, args.results_dir)
        size_str = f"{size/1000:.0f}K cells" if size else "size unknown"
        logger.info(f"  {f.dataset_name} ({size_str}, current: {f.current_preset.value})")

    if args.check:
        return

    if args.resubmit:
        if args.dry_run:
            logger.info("\nDry run - would generate resubmission script with:")
            for f in failures:
                new_preset = escalate_preset(f.current_preset)
                if new_preset:
                    config = get_config(new_preset)
                    logger.info(f"  {f.dataset_name}: {f.current_preset.value} -> {new_preset.value} ({config.mem_gb}GB)")
        else:
            generate_resubmission_script(
                failures=failures,
                script_path=args.output_script,
                command_template=args.command,
                results_dir=args.results_dir,
            )


if __name__ == "__main__":
    main()
