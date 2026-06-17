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
#BSUB -W 12:00                 # wall-clock limit HH:MM
#BSUB -M 32000                 # memory limit in MB (32 GB)
#BSUB -J dp_rve_steel          # job name
#BSUB -o logs/dp_rve_%J.out    # stdout  (%J = jobid)
#BSUB -e logs/dp_rve_%J.err    # stderr

# ── Safety: abort on any error ──────────────────────────────
set -euo pipefail
# Ensure local GCC runtime & HDF5/FFTW libs are visible
export LD_LIBRARY_PATH="$HOME/local/gcc-13.2.0/lib64:$HOME/local/gcc-13.2.0/lib:$HOME/local/hdf5-1.14.5-gcc13-ompi416/lib:$HOME/local/fftw-3.3.10-gcc13-ompi416/lib:${LD_LIBRARY_PATH:-}"
# DAMASK grid install prefix
export DAMASK_PREFIX="$HOME/local/damask-3.0.2"
export PATH="$DAMASK_PREFIX/bin:$PATH"


# ── Activate environment ─────────────────────────────────────
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate micro_dpsteel

# ── OpenMP / BLAS thread control ────────────────────────────
# n_workers=2, n_threads=4  →  2×4 = 8 solver threads
# Must not exceed (bsub -n) = 16
export OMP_NUM_THREADS=4       # matches damask.n_threads in config #It speeds up damask's solver

# ── Project directory ────────────────────────────────────────
PIPELINE_DIR="/home/toso3816/src/dp_steel_rve"
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
