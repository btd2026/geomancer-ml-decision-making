#!/bin/bash
#SBATCH --job-name=preprocess_geo
#SBATCH --output=/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/logs/preprocess_%A_%a.out
#SBATCH --error=/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/logs/preprocess_%A_%a.err
#SBATCH --array=0-49%10  # 50 parallel workers, max 10 concurrent
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=8:00:00
#SBATCH --partition=day

# Exit on error
set -e

# Create directories
mkdir -p /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/logs
mkdir -p /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/preprocessed

# Activate virtual environment
export PATH="$HOME/.local/bin:$PATH"
cd /home/btd8/manylatents
source .venv/bin/activate

echo "========================================="
echo "Preprocessing Task ID: ${SLURM_ARRAY_TASK_ID}"
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "========================================="

# Run preprocessing for this task's share of files
# 101 datasets / 50 tasks = ~2 files per task
# Script is in geomancer project, run with full path
python /home/btd8/GitHub/geomancer-ml-decision-making/scripts/preprocess_all_datasets.py \
    --input-dir /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/processed \
    --output-dir /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/preprocessed \
    --max-cells 50000 \
    --task-id ${SLURM_ARRAY_TASK_ID} \
    --n-tasks 50 \
    --report /nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/preprocessed/report_task_${SLURM_ARRAY_TASK_ID}.json

echo ""
echo "========================================="
echo "Task completed: ${SLURM_ARRAY_TASK_ID}"
echo "Date: $(date)"
echo "========================================="
