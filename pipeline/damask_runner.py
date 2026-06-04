"""
pipeline/damask_runner.py
Run DAMASK for all samples that have a completed Neper tessellation.

Execution model
---------------
DAMASK_grid is already parallelized internally via OpenMP (OMP_NUM_THREADS).
Therefore we run ONE sample at a time in the outer loop — using
ProcessPoolExecutor with max_workers=1 keeps the interface consistent with
neper_runner but avoids CPU over-subscription.

If you have multiple compute nodes, set n_workers > 1 only when each node
has its own CPU allocation and OMP_NUM_THREADS is set per node.

Workflow per sample
-------------------
1. Check StateManager — skip if DONE, skip neper if not DONE.
2. Set status RUNNING.
3. Call damask.grid_builder.build_geom_from_neper()
4. Call damask.material_writer.write_material_yaml()
5. Call damask.load_writer.write_load_yaml()
6. Call damask.solver.run_solver()
7. Set status DONE / FAILED.
"""

from __future__ import annotations

import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from pipeline.state_manager   import StateManager
from utils.logger             import get_logger
from utils.paths              import ensure_dir

log = get_logger(__name__)


def run_damask_stage(
    dataset:         object,         # pd.DataFrame
    dataset_dir:     str | Path,
    state:           StateManager,
    rve_size_m,                      # np.ndarray  shape (3,)
    damask_module,                   # imported damask package
    damask_executable: str = "DAMASK_grid",
    n_threads:         int = 4,
    n_workers:         int = 1,
    dry_run:           bool = False,
    retry_failed:      bool = False,
) -> dict:
    """
    Run DAMASK grid solver for all Neper-complete samples.

    Parameters
    ----------
    dataset          : pd.DataFrame
    dataset_dir      : Path — N_<n> folder
    state            : StateManager
    rve_size_m       : array-like shape (3,) — physical RVE size in metres
    damask_module    : the imported `damask` Python package
    damask_executable: str — name or path of DAMASK_grid binary
    n_threads        : int — OMP_NUM_THREADS per solver call
    n_workers        : int — parallel samples (default 1, see note above)
    dry_run          : bool
    retry_failed     : bool

    Returns
    -------
    dict {"done": int, "failed": int, "skipped": int}
    """
    dataset_dir = Path(dataset_dir)

    if retry_failed:
        n_reset = state.reset_failed("damask")
        log.info("Retry mode: reset %d FAILED → PENDING (damask)", n_reset)

    # Only process samples whose neper stage is DONE
    pending = [
        sid for sid in state.pending_ids("damask")
        if state.is_done(sid, "neper")
    ]
    neper_not_ready = len(state.pending_ids("damask")) - len(pending)
    if neper_not_ready:
        log.warning("%d samples skipped: neper not yet DONE", neper_not_ready)

    log.info("DAMASK stage: %d samples pending  (workers=%d  threads=%d  dry_run=%s)",
             len(pending), n_workers, n_threads, dry_run)

    if not pending:
        log.info("Nothing to do for damask stage.")
        return {"done": 0, "failed": 0, "skipped": neper_not_ready}

    results = {"done": 0, "failed": 0, "skipped": neper_not_ready}

    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(
                _damask_worker,
                sample_id          = sid,
                sample_row         = dataset.iloc[sid],
                dataset_dir        = dataset_dir,
                rve_size_m         = rve_size_m,
                damask_module      = damask_module,
                damask_executable  = damask_executable,
                n_threads          = n_threads,
                dry_run            = dry_run,
            ): sid
            for sid in pending
        }

        for future in as_completed(futures):
            sid = futures[future]
            try:
                outcome = future.result()
                state.set_status(sid, "damask", outcome)
                if outcome == "DONE":
                    results["done"] += 1
                else:
                    results["failed"] += 1
            except Exception as exc:
                log.error("DAMASK worker raised for sample %04d: %s", sid, exc)
                state.set_status(sid, "damask", "FAILED")
                results["failed"] += 1

    state.print_summary()
    return results


def _damask_worker(
    sample_id:        int,
    sample_row:       object,
    dataset_dir:      Path,
    rve_size_m,
    damask_module,
    damask_executable: str,
    n_threads:         int,
    dry_run:           bool,
) -> str:
    """Single-sample DAMASK worker (runs in a subprocess)."""
    from damask.grid_builder    import build_geom_from_neper
    from damask.material_writer import write_material_yaml
    from damask.load_writer     import write_load_yaml
    from damask.solver          import run_solver

    sample_dir = dataset_dir / f"sample_{sample_id:04d}"

    if dry_run:
        log.info("DRY RUN — DAMASK sample %04d  (skipping execution)", sample_id)
        return "DONE"

    try:
        build_geom_from_neper(sample_dir, damask_module, rve_size_m)
        write_material_yaml(sample_row, sample_dir, damask_module)
        write_load_yaml(sample_row, sample_dir)
        run_solver(
            sample_dir  = sample_dir,
            executable  = damask_executable,
            n_threads   = n_threads,
        )
        return "DONE"
    except Exception:
        log.error("DAMASK FAILED sample %04d:\n%s", sample_id, traceback.format_exc())
        return "FAILED"
