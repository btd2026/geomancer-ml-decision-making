#!/bin/bash
#SBATCH --job-name=dse_missing
#SBATCH --array=0-14%10
#SBATCH --mem=64G
#SBATCH --cpus-per-task=4
#SBATCH --time=02:00:00
#SBATCH --partition=day
#SBATCH --output=logs/dse_missing_%a.out
#SBATCH --error=logs/dse_missing_%a.err

# DSE metrics for 15 runs that are missing them
# Generated 2026-03-04

source /home/btd8/manylatents/.venv/bin/activate

DATASETS=("All-snRNA-Spatial_multi-omic_map_of_human_myocardi_1c739a3e__default_xlarge_20260303_075259" "ClassNeuroblast_e59a4394__default_xlarge_20260303_175721" "Combined_single_cell_and_single_nuclei_RNA-Seq_dat_d567b692__default_xlarge_20260303_180117" "Excitatory_215ede73__default_xlarge_20260303_180917" "HypoMap___a_unified_single_cell_gene_expression_at_dbb4e1ed__default_xlarge_20260303_181316" "L2_3_IT_-_DLPFC__Seattle_Alzheimer_s_Disease_Atlas_646e3e87__default_xlarge_20260303_181817" "L2_3_IT_-_MTG__Seattle_Alzheimer_s_Disease_Atlas___b74100ea__default_xlarge_20260303_182518" "Supercluster__Oligodendrocyte_40e79234__default_xlarge_20260303_183716" "Supercluster__Splatter_3a7f3ab4__default_xlarge_20260303_184517" "Tabula_Sapiens_-_Epithelium_97a17473__default_xlarge_20260303_185018" "Tabula_Sapiens_-_Stromal_a68b64d8__default_xlarge_20260303_185517" "Telencephalon_675873e1__default_xlarge_20260303_185918" "all_cells_cff99df2__default_xlarge_20260303_175021" "snRNA-seq_of_human_retina_-_retinal_ganglion_cell_95ce06a0__default_xlarge_20260303_183115" "thymus_scRNA-seq_atlas_29244e1d__default_xlarge_20260303_190416")
DATASET_NAME=${DATASETS[$SLURM_ARRAY_TASK_ID]}

echo "Processing: $DATASET_NAME"

python scripts/dse/run_dse_metrics.py configs/dse_metrics_experiments.yaml --local --dataset "$DATASET_NAME"

echo "Done: $DATASET_NAME"
