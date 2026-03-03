#!/usr/bin/env python3
"""
Re-submit failed PHATE jobs with xlarge resources (general partition, 24hr).
"""

import json
import subprocess
import time
from pathlib import Path

# List of failed datasets
failed_datasets = [
    "All_-_A_single-cell_transcriptomic_atlas_character_f16a8f4d",
    "All_cells_and_nuclei_093d3bfe",
    "All_Cells_-_snRNA-seq_ac0c6561",
    "All_donors_all_cell_states__in_vivo__74cff64f",
    "All_major_cell_types_in_adult_human_retina_0129dbd9",
    "All-snRNA-Spatial_multi-omic_map_of_human_myocardi_1c739a3e",
    "An_integrated_transcriptomic_and_epigenomic_atlas_35081d47",
    "A_Single-Cell_Atlas_of_Mouse_White_Adipose_Tissue_a2da8d7b",
    "Atlas_of_the_developing_mouse_thalamus_79a2344d",
    "Blood_d86edd6a",
    "Carebank_8f4f8502",
    "Circulating_Immune_cells_--_CV19_infection__vaccin_242c6e7f",
    "Core_GBmap_c888b684",
    "COVID-19_Immune_Altas__Integration_of_5_public_COV_96a3f64b",
    "DCM_ACM_heart_cell_atlas__Cardiomyocytes_f7995301",
    "Dissection__Primary_visual_cortex_V1__8d1dd010",
    "Figure_1_-_A_cell_atlas_of_human_thymic_developmen_cda2c8cd",
    "Frozen_samples__single_nucleus__34f5307e",
    "Global_1b9d8702",
    "HBCA_-_epithelial_975e13b6",
    "HBCA_-_stroma_be35c935",
    "Human_CellCards_Multi-Study_CellRef_1_0_Atlas_eb499fd8",
    "Human_Female_18e2a8c5",
    "Human_healthy_adult_skin_scRNA-seq_data_f0f0d7c4",
    "human_intestine_organoid_cell_atlas_776a1e4a",
    "human_lung_organoid_cell_atlas_569bce19",
    "Human_Somatic_Cell_Lineage_4fb330ab",
    "Integrated_cancer_cell-specific_single-cell_RNA-se_7b20c613",
    "Integrated_Single-nucleus_and_Single-cell_RNA-seq_0b75c598",
    "Intestine_cbec7853",
    "Kidney_f95d8919",
    "Liver_1d89d081",
    "Lung_493a8b60",
    "Lymphoid_cells_3affa268",
    "Major_cell_cluster__Endothelium_361eef7c",
    "Major_cell_cluster__Hepatocytes_977e6167",
    "Major_cell_cluster__Muscle_cells_eaa7a0b0",
    "Major_cell_cluster__White_blood_cells_c34e5efb",
    "Midbrain_bfbd9097",
    "Mouse_--_all_cells_7b6bab5a",
    "mouse_limb_scRNAseq_4c4cfb38",
    "Mouse_pancreatic_islet_scRNA-seq_atlas_across_sexe_49e4ffcc",
    "MRCA__scRNA-seq_of_the_mouse_retina_-_all_cells_23f77ae6",
    "MSK_SPECTRUM_-_CD4__T_cells__CD8__T_cells__ILCs_an_e3a7e927",
    "MSK_SPECTRUM_-_Malignant_and_non-malignant_epithel_44c93f2b",
    "Myeloid_cells_2aa1c93c",
    "Oral_and_Craniofacial_Atlas_cb252df6",
    "PBMC_2a498ace",
    "Periheart_f1606894",
    "plaque_atlas_72955cdb",
    "scRNA-seq_data_-_epithelial_cells_2a7f90de",
    "scRNA-seq_data_-_fibroblasts_3d0d6923",
    "scRNA-seq_of_human_retina_-_all_cells_be41a86a",
    "Second_Trimester_Human_Developing_Brain_Regions_an_ae4f8ddd",
    "Single-cell_RNA-seq_of_the_Adult_Human_Kidney__Ver_dea717d4",
    "Single-cell_transcriptomic_datasets_of_Renal_cell_5af90777",
    "Single-nucleus_cross-tissue_molecular_reference_ma_4ed927e9",
    "Single-nucleus_RNA-seq_of_the_Adult_Human_Kidney___a12ccb9b",
    "Single-nucleus_RNA_sequencing_of_M2__WT-THR_vs_DN-_1229ecc2",
    "Skeletal_muscle_15d374d6",
    "Spleen_72f4798d",
    "Stromal_cells__all_non-immune_cells__d0c12af4",
    "Supercluster__CGE_interneuron_bdb26abd",
    "Supercluster__Deep-layer_intratelencephalic_98113e7e",
    "Supercluster__MGE_interneuron_e4710a02",
    "Supercluster__Upper-layer_intratelencephalic_0325478a",
]

# XLarge resources (general partition allows 24hr)
resources = {
    "mem_gb": 256,
    "cpus_per_task": 24,
    "timeout_min": 1440,  # 24 hours for large datasets
    "partition": "general"
}

configs_dir = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results/_configs")

submitted = 0
failed = 0

for dataset in failed_datasets:
    config_path = configs_dir / f"{dataset}_default.json"

    if not config_path.exists():
        print(f"Config not found: {config_path}")
        continue

    # Update config to use xlarge resources
    with open(config_path) as f:
        config = json.load(f)

    # Add a note about rerun
    config["run_name"] = "default_xlarge"
    config["phate_params"]["n_pca"] = 100  # Use PCA to speed up KNN

    # Save updated config
    rerun_config_path = configs_dir / f"{dataset}_default_xlarge.json"
    with open(rerun_config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # Submit to SLURM
    # Format timeout as HH:MM:SS (e.g., 360 min = 06:00:00 = 6 hours)
    hours = resources["timeout_min"] // 60
    minutes = resources["timeout_min"] % 60
    time_str = f"{hours:02d}:{minutes:02d}:00"

    cmd = f"python scripts/phate/run_phate_organized.py {rerun_config_path}"
    sbatch_cmd = [
        "sbatch",
        "--partition", resources["partition"],
        "--mem", f"{resources['mem_gb']}G",
        "--cpus-per-task", str(resources["cpus_per_task"]),
        "--time", time_str,
        "--job-name", f"phate_{dataset[:30]}",
        "--wrap", cmd,
    ]

    result = subprocess.run(sbatch_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Submitted: {dataset}")
        submitted += 1
    else:
        print(f"Failed: {dataset} - {result.stderr}")
        failed += 1

    # Brief pause between submissions
    time.sleep(3)

print(f"\nDone: {submitted} submitted, {failed} failed")
