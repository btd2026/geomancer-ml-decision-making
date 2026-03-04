#!/usr/bin/env python3
"""
Re-submit OOM-killed PHATE jobs with xlarge resources (256GB, 24hr, general partition).

These jobs failed because they used the 'medium' preset (128GB) but needed more memory
for large datasets (>200K cells).
"""

import json
import subprocess
import time
from pathlib import Path

# OOM-killed configs from batch 5457*
OOM_FAILED_CONFIGS = [
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/all_cells_cff99df2_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/ClassNeuroblast_e59a4394_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Combined_single_cell_and_single_nuclei_RNA-Seq_dat_d567b692_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Excitatory_215ede73_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/HypoMap___a_unified_single_cell_gene_expression_at_dbb4e1ed_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/L2_3_IT_-_DLPFC__Seattle_Alzheimer_s_Disease_Atlas_646e3e87_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/L2_3_IT_-_MTG__Seattle_Alzheimer_s_Disease_Atlas___b74100ea_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/snRNA-seq_of_human_retina_-_retinal_ganglion_cell_95ce06a0_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Supercluster__Oligodendrocyte_40e79234_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Supercluster__Splatter_3a7f3ab4_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Tabula_Sapiens_-_Epithelium_97a17473_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Tabula_Sapiens_-_Stromal_a68b64d8_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/Telencephalon_675873e1_default_retry2.json",
    "/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs/thymus_scRNA-seq_atlas_29244e1d_default_retry2.json",
]

# XLarge resources: 256GB RAM, 24 CPUs, 25hr timeout, week partition
XLARGE_RESOURCES = {
    "mem_gb": 256,
    "cpus_per_task": 24,
    "timeout_min": 1500,  # 25 hours (week partition requires >= 24hr)
    "partition": "week"  # Allows up to 7 days
}


def create_xlarge_config(original_config_path: str) -> Path:
    """Create a new config with xlarge run name."""
    original_path = Path(original_config_path)

    if not original_path.exists():
        print(f"WARNING: Config not found: {original_path}")
        return None

    # Load original config
    with open(original_path) as f:
        config = json.load(f)

    # Update run name to indicate xlarge retry
    original_run_name = config.get("run_name", "default")
    config["run_name"] = "default_xlarge"

    # Ensure phate params are set for large datasets
    if "phate_params" not in config:
        config["phate_params"] = {}
    config["phate_params"]["n_pca"] = 100  # Reduce memory during KNN

    # Create new config path
    dataset_name = original_path.stem.replace("_default_retry2", "").replace("_default", "")
    new_config_path = original_path.parent / f"{dataset_name}_default_xlarge.json"

    # Save new config
    with open(new_config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Created config: {new_config_path}")
    return new_config_path


def submit_job(config_path: Path, dry_run: bool = False) -> bool:
    """Submit a SLURM job with xlarge resources."""
    mem_gb = XLARGE_RESOURCES["mem_gb"]
    cpus = XLARGE_RESOURCES["cpus_per_task"]
    timeout = XLARGE_RESOURCES["timeout_min"]
    partition = XLARGE_RESOURCES["partition"]

    # Format timeout as HH:MM:SS
    hours = timeout // 60
    minutes = timeout % 60
    time_str = f"{hours:02d}:{minutes:02d}:00"

    cmd = f"python scripts/phate/run_phate_organized.py {config_path}"

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
        return True

    result = subprocess.run(sbatch_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Submitted: {result.stdout.strip()}")
        return True
    else:
        print(f"FAILED: {result.stderr}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Resubmit OOM-killed jobs with xlarge resources")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without submitting")
    args = parser.parse_args()

    print(f"Processing {len(OOM_FAILED_CONFIGS)} OOM-killed jobs")
    print(f"Resources: {XLARGE_RESOURCES}")
    print()

    submitted = 0
    failed = 0

    for original_config in OOM_FAILED_CONFIGS:
        new_config = create_xlarge_config(original_config)

        if new_config is None:
            failed += 1
            continue

        if submit_job(new_config, dry_run=args.dry_run):
            submitted += 1
        else:
            failed += 1

        # Brief pause between submissions
        time.sleep(2)

    print()
    print(f"Done: {submitted} submitted, {failed} failed")


if __name__ == "__main__":
    main()
