#!/usr/bin/env bash
# ============================================================
#  run_hpc_array.sh — LSF JOB ARRAY for dp_steel_rve
#  Cluster: Makalu / BatchXL
#
#  Generates 1000 samples across 20 array tasks × 50 samples each.
#
#  Submit:
#      bsub < run_hpc_array.sh
#
#  Monitor:
#      bjobs -A dp_rve_array
#      bpeek dp_rve_array[3]     # tail stdout of task 3
# ============================================================

#BSUB -q BatchXL
#BSUB -J dp_rve_array[1-20]%20      # 20 tasks, all can run concurrently
#BSUB -n 16                         # 16 cores per task
#BSUB -R "span[hosts=1]"            # CRITICAL: all 16 cores on ONE node
#BSUB -R "select[cores>=16]"        # only allocate nodes with ≥16 physical cores
#BSUB -W 36:00                      # wall-clock per task (50 samples × ~30 min)
#BSUB -M 64000                      # memory per task (MB)
#BSUB -o logs/array_%J_%I.out       # %J=jobid  %I=array index
#BSUB -e logs/array_%J_%I.err


set -euo pipefail
ulimit -s unlimited


# ── Paths & environment ──────────────────────────────────────
export LD_LIBRARY_PATH="$HOME/local/gcc-13.2.0/lib64:$HOME/local/gcc-13.2.0/lib:\
$HOME/local/hdf5-1.14.5-gcc13-ompi416/lib:\
$HOME/local/fftw-3.3.10-gcc13-ompi416/lib:${LD_LIBRARY_PATH:-}"

export DAMASK_PREFIX="$HOME/local/damask-3.0.2"
export PATH="$DAMASK_PREFIX/bin:$HOME/local/hdf5-1.14.5-gcc13-ompi416/bin:$PATH"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate micro_dpsteel

# ── OpenMP (DAMASK internal solver threads) ──────────────────
export OMP_NUM_THREADS=4            # 4 workers × 4 threads = 16 cores total
export OMP_PROC_BIND=close          # bind threads to nearby cores (cache reuse)
export OMP_PLACES=cores             # pin to physical cores, not hyperthreads

# ── Prevent OpenMP/BLAS thread oversubscription ──────────────
export MKL_NUM_THREADS=4            # Intel MKL (if used by numpy/scipy)
export OPENBLAS_NUM_THREADS=4       # OpenBLAS fallback
export BLAS_NUM_THREADS=4
export VECLIB_MAXIMUM_THREADS=4     # macOS vecLib (harmless on Linux)
export NUMEXPR_NUM_THREADS=4        # numexpr (used by pandas/h5py internally)

# ── Prevent numpy from spawning extra threads ─────────────────
export OMP_STACKSIZE=512M           # DAMASK uses deep OpenMP call stacks

# ── HDF5 / FFTW tuning ───────────────────────────────────────
export HDF5_USE_FILE_LOCKING=TRUE   # safe for single-node; FALSE only on Lustre
export FFTW_WISDOM_DIR="$HOME/.fftw_wisdom"   # reuse FFTW plan cache across tasks

# ── Python / process tuning ──────────────────────────────────
export PYTHONFAULTHANDLER=1         # dump traceback on segfault (debug aid)
export PYTHONUNBUFFERED=1           # flush stdout/stderr immediately to log files
export MALLOC_TRIM_THRESHOLD_=0     # return freed memory to OS promptly
                                    # important when 4 workers × large HDF5 loads


PIPELINE_DIR="/home/toso3816/src/dp_steel_rve"
cd "${PIPELINE_DIR}"
mkdir -p logs "${FFTW_WISDOM_DIR}"




# ── Task info ────────────────────────────────────────────────
echo "=== ARRAY TASK INFO ==="
echo "JobID:      ${LSB_JOBID:-unknown}"
echo "ArrayIndex: ${LSB_JOBINDEX:-unknown}"
echo "Host:       $(hostname)"
echo "Date:       $(date)"
echo "Cores:      $(nproc)"
echo "OMP:        ${OMP_NUM_THREADS}"
echo "======================="

# ── Run pipeline slice ───────────────────────────────────────
python main.py \
    --config      ./configs/pipeline_config_hpc.yaml \
    --env         linux \
    --stage       all \
    --batch-index "${LSB_JOBINDEX}" \
    --batch-size  50 \
    --n-samples   1000 \
    --retry-failed

echo "Task ${LSB_JOBINDEX} finished: $(date)"