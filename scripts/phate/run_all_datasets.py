#!/usr/bin/env python3
"""
Batch runner for PHATE experiments using the config file.

Reads configs/phate_experiments.yaml, generates JSON run configs,
and submits jobs to SLURM.
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import h5py
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict[str, Any]:
    """Load the YAML config file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_dataset_n_obs(h5ad_path: Path) -> int | None:
    """Get number of observations (cells) from H5AD file without loading full data."""
    try:
        with h5py.File(h5ad_path, 'r') as f:
            # H5AD stores shape in obs and var groups
            # Try different ways to get n_obs

            # Method 1: Check for _index in obs (AnnData native format)
            if 'obs' in f:
                if '_index' in f['obs']:
                    index_data = f['obs']['_index']
                    if hasattr(index_data, 'shape'):
                        return index_data.shape[0]
                    elif hasattr(index_data, 'len'):
                        return len(index_data)

                # Method 2: Try to get length from any obs column
                for key in f['obs'].keys():
                    col_data = f['obs'][key]
                    if hasattr(col_data, 'shape'):
                        return col_data.shape[0]
                    elif hasattr(col_data, 'len'):
                        return len(col_data)

            # Method 3: Check X matrix shape
            if 'X' in f:
                x_data = f['X']
                if hasattr(x_data, 'shape'):
                    return x_data.shape[0]

            return None
    except Exception as e:
        logger.warning(f"Could not read n_obs from {h5ad_path}: {e}")
        return None


def select_preset_for_dataset(
    h5ad_path: Path,
    presets: dict,
    default_preset: str = "medium",
) -> tuple[str, dict]:
    """
    Auto-select SLURM preset based on dataset size.

    Thresholds:
    - >200K cells: xlarge (256GB, 24hr, general partition)
    - >100K cells: large (256GB, 8hr, day partition)
    - <=100K cells: use default preset

    Returns: (preset_name, resources_dict)
    """
    n_obs = get_dataset_n_obs(h5ad_path)

    if n_obs is None:
        logger.warning(f"Could not determine dataset size, using default preset: {default_preset}")
        return default_preset, presets.get(default_preset, presets["medium"])

    if n_obs > 200000:
        preset_name = "xlarge"
        logger.info(f"Large dataset ({n_obs:,} cells) -> using {preset_name} preset")
    elif n_obs > 100000:
        preset_name = "large"
        logger.info(f"Medium-large dataset ({n_obs:,} cells) -> using {preset_name} preset")
    else:
        preset_name = default_preset
        logger.info(f"Standard dataset ({n_obs:,} cells) -> using {preset_name} preset")

    return preset_name, presets.get(preset_name, presets["medium"])


def generate_run_config(
    dataset: dict,
    run: dict,
    base_config: dict,
    output_dir: str,
    slurm_preset: str,
    presets: dict,
) -> Path:
    """Generate a JSON config file for a single run."""
    run_name = run["name"]
    dataset_name = dataset["name"]

    # Build run configuration
    run_config = {
        "h5ad_path": str(Path(base_config["h5ad_base_dir"]) / dataset["h5ad_file"]),
        "dataset_name": dataset_name,
        "output_base_dir": output_dir,
        "run_name": run_name,
        "description": dataset.get("description", dataset_name),
        "label_key": run.get("label_key", base_config.get("defaults", {}).get("label_key", "auto")),
        "phate_params": {
            **base_config.get("defaults", {}).get("phate", {}),
            **run.get("phate_params", {}),
        },
        "wandb": base_config.get("wandb", {
            "entity": "cesar-valdez-mcgill-university",
            "project": "manylatent-2026-brian",
        }),
    }

    # Save JSON config
    jsons_dir = Path(output_dir) / "_configs"
    jsons_dir.mkdir(parents=True, exist_ok=True)

    config_path = jsons_dir / f"{dataset_name}_{run_name}.json"
    with open(config_path, 'w') as f:
        json.dump(run_config, f, indent=2)

    logger.info(f"Generated config: {config_path}")
    return config_path


def submit_job(
    config_path: Path,
    resources: dict,
    dry_run: bool = False,
) -> int:
    """Submit a single SLURM job."""
    mem_gb = resources.get("mem_gb", 64)
    cpus = resources.get("cpus_per_task", 8)
    timeout = resources.get("timeout_min", 240)
    partition = resources.get("partition", "day")

    # Command to run PHATE with JSON config
    cmd = f"python scripts/phate/run_phate_organized.py {config_path}"

    # Format timeout as HH:MM:SS
    hours = timeout // 60
    minutes = timeout % 60
    time_str = f"{hours:02d}:{minutes:02d}:00"

    sbatch_cmd = [
        "sbatch",
        "--partition", partition,
        "--mem", f"{mem_gb}G",
        "--cpus-per-task", str(cpus),
        "--time", time_str,
        "--job-name", f"phate_{config_path.stem[:30]}",
        "--wrap", cmd,
    ]

    if dry_run:
        print(f"Would submit: {' '.join(sbatch_cmd)}")
        return 0

    result = subprocess.run(sbatch_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Submitted job: {result.stdout.strip()}")
        return 0
    else:
        logger.error(f"Failed to submit: {result.stderr}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Batch run PHATE experiments from config")
    parser.add_argument(
        "config",
        type=Path,
        default=Path("configs/phate_experiments.yaml"),
        help="Path to config YAML",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without submitting")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of datasets")
    parser.add_argument("--offset", type=int, default=0, help="Start from this dataset index")
    parser.add_argument("--generate-only", action="store_true", help="Only generate JSON configs, don't submit")

    args = parser.parse_args()

    config = load_config(args.config)

    output_dir = config["output_dir"]
    defaults = config.get("defaults", {})
    slurm_presets = config.get("slurm_presets", {})
    datasets = config.get("datasets", [])

    # Apply limit and offset
    if args.offset:
        datasets = datasets[args.offset:]
    if args.limit:
        datasets = datasets[:args.limit]

    logger.info(f"Processing {len(datasets)} datasets from offset {args.offset}")

    # Create configs directory
    jsons_dir = Path(output_dir) / "_configs"
    jsons_dir.mkdir(parents=True, exist_ok=True)

    # Generate all JSON configs and collect jobs to submit
    jobs_to_submit = []
    for dataset in datasets:
        dataset_name = dataset["name"]
        runs = dataset.get("runs", [{"name": "default"}])

        # Get h5ad path for auto-preset selection
        h5ad_path = Path(config["h5ad_base_dir"]) / dataset["h5ad_file"]

        for run in runs:
            run_name = run["name"]

            # Auto-select preset based on dataset size, unless explicitly specified
            explicit_preset = run.get("slurm_preset")
            if explicit_preset:
                slurm_preset = explicit_preset
                resources = slurm_presets.get(slurm_preset, slurm_presets["medium"])
                logger.info(f"Using explicit preset '{slurm_preset}' for {dataset_name}")
            else:
                slurm_preset, resources = select_preset_for_dataset(
                    h5ad_path,
                    slurm_presets,
                    defaults.get("slurm_preset", "medium"),
                )

            config_path = generate_run_config(
                dataset=dataset,
                run=run,
                base_config=config,
                output_dir=output_dir,
                slurm_preset=slurm_preset,
                presets=slurm_presets,
            )

            jobs_to_submit.append({
                "config_path": config_path,
                "resources": resources,
                "dataset": dataset_name,
                "run": run_name,
                "preset": slurm_preset,
            })

    # Save manifest of all generated configs
    manifest_path = jsons_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({
            "total_jobs": len(jobs_to_submit),
            "jobs": [
                {
                    "dataset": j["dataset"],
                    "run": j["run"],
                    "config": str(j["config_path"]),
                    "preset": j["preset"],
                    "resources": j["resources"],
                }
                for j in jobs_to_submit
            ],
        }, f, indent=2)

    logger.info(f"Generated {len(jobs_to_submit)} JSON configs in {jsons_dir}")

    if args.generate_only:
        logger.info("Generated configs only, not submitting jobs")
        return 0

    # Submit jobs
    submitted = 0
    failed = 0

    for job in jobs_to_submit:
        max_retries = 10
        for attempt in range(max_retries):
            ret = submit_job(
                config_path=job["config_path"],
                resources=job["resources"],
                dry_run=args.dry_run,
            )

            if ret == 0:
                submitted += 1
                break
            elif "QOS" in str(ret) or "Limit" in str(ret):
                wait_time = 60 * (attempt + 1)
                logger.info(f"SLURM queue full, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                failed += 1
                break

        # Brief pause between submissions
        time.sleep(5)

    logger.info(f"Done: {submitted} submitted, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
