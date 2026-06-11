#!/usr/bin/env bash
# ============================================================
#  run_hpc.sh — LSF job script for dp_steel_rve pipeline
#  Cluster: Makalu / BatchXL  (64-slot Xeon/EPYC nodes)
#
#  Usage (single-job, all samples):
#      bsub < run_hpc.sh
#
#  Usage (override n_samples):
#      bsub -env "N_SAMPLES=100" < run_hpc.sh
# ============================================================

# ── LSF directives ──────────────────────────────────────────
#BSUB -q BatchXL               # queue
#BSUB -n 16                    # number of job slots (cores)
#BSUB -W 08:00                 # wall-clock limit HH:MM
#BSUB -M 32000                 # memory limit in MB (32 GB)
#BSUB -J dp_rve_steel          # job name
#BSUB -o logs/dp_rve_%J.out    # stdout  (%J = jobid)
#BSUB -e logs/dp_rve_%J.err    # stderr

# ── Safety: abort on any error ──────────────────────────────
set -euo pipefail

# ── Activate environment ─────────────────────────────────────
module load python/anaconda3
conda activate micro_dpsteel

# ── OpenMP / BLAS thread control ────────────────────────────
# n_workers=2, n_threads=4  →  2×4 = 8 solver threads
# Must not exceed (bsub -n) = 16
export OMP_NUM_THREADS=4       # matches damask.n_threads in config
export OMP_PROC_BIND=spread    # pin threads to spread across cores
export OMP_PLACES=cores        # thread placement unit = physical core
export OMP_DYNAMIC=FALSE       # never let OpenMP change thread count silently
export MKL_NUM_THREADS=4       # keep BLAS libraries in line
export OPENBLAS_NUM_THREADS=1  # prevent nested BLAS oversubscription

# ── Project directory ────────────────────────────────────────
PIPELINE_DIR="/home/toso3816/src/_/src"    # adjust to your repo location
cd "${PIPELINE_DIR}"

# ── Create log directory if missing ─────────────────────────
mkdir -p logs

# ── Optional: print resource info for debugging ─────────────
echo "=== JOB INFO ==="
echo "Host:      $(hostname)"
echo "Date:      $(date)"
echo "Cores:     $(nproc)"
echo "OMP:       ${OMP_NUM_THREADS}"
echo "JOBID:     ${LSB_JOBID:-unknown}"
echo "================"

# ── Run pipeline ─────────────────────────────────────────────
python main.py \
    --config ./configs/pipeline_config_hpc.yaml \
    --env    linux \
    --stage  all

echo "Pipeline finished: $(date)"
