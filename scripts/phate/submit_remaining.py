#!/usr/bin/env python3
"""
Submit remaining PHATE jobs in small batches.
"""

import json
import subprocess
import time
from pathlib import Path

# Get all datasets from configs
configs_dir = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs")
results_dir = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results")

# Get completed datasets
completed = set()
for emb in results_dir.glob("*/runs/*/embedding.csv"):
    dataset = emb.parent.parent.parent.name
    completed.add(dataset)

print(f"Completed: {len(completed)} datasets")

# Get all datasets from default configs (not xlarge)
all_configs = sorted(configs_dir.glob("*_default.json"))
pending = []
for config_path in all_configs:
    dataset = config_path.stem.replace("_default", "")
    if dataset not in completed:
        pending.append((dataset, config_path))

print(f"Pending: {len(pending)} datasets")

# Resources: Use scavenge partition (can be pre-empted but more available)
resources = {
    "mem_gb": 128,
    "cpus_per_task": 16,
    "timeout_min": 240,
    "partition": "scavenge"
}

# Submit jobs one at a time with longer delays
submitted = 0
failed = 0

for dataset, config_path in pending[50:]:  # Rest
    # Update config to use n_pca for speed
    with open(config_path) as f:
        config = json.load(f)

    config["run_name"] = "default_retry"
    config["phate_params"]["n_pca"] = 100

    # Save updated config
    retry_config_path = configs_dir / f"{dataset}_default_retry.json"
    with open(retry_config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # Submit to SLURM
    hours = resources["timeout_min"] // 60
    minutes = resources["timeout_min"] % 60
    time_str = f"{hours:02d}:{minutes:02d}:00"

    cmd = f"python scripts/phate/run_phate_organized.py {retry_config_path}"
    sbatch_cmd = [
        "sbatch",
        "--partition", resources["partition"],
        "--mem", f"{resources['mem_gb']}G",
        "--cpus-per-task", str(resources["cpus_per_task"]),
        "--time", time_str,
        "--job-name", f"phate_{dataset[:25]}",
        "--wrap", cmd,
    ]

    print(f"Submitting: {dataset}")
    result = subprocess.run(sbatch_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        jobid = result.stdout.strip().split()[-1]
        print(f"  -> Job {jobid}")
        submitted += 1
    else:
        print(f"  -> Failed: {result.stderr}")
        failed += 1

    # Longer delay between submissions
    time.sleep(10)

print(f"\nDone: {submitted} submitted, {failed} failed")
