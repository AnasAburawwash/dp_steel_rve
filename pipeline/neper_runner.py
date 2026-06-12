"""
pipeline/neper_runner.py
Run Neper tessellation + visualization for all samples in one dataset.

Execution model
---------------
Uses concurrent.futures.ProcessPoolExecutor to run Neper instances in parallel.
Each worker is independent: Neper is a single-process CLI tool, so N_WORKERS
simultaneous Neper processes scale well up to the available CPU count.

Workflow per sample
-------------------
1. Check StateManager — skip if already DONE.
2. Set status RUNNING.
3. Call neper.run_tessellation(sample_row, sample_dir, cfg).
4. Call neper.run_visualization(tess_file, sample_id, sample_dir, vis_cfg) — non-blocking.
5. Set status DONE / FAILED.

Resume and retry
----------------
--resume      : skips DONE samples, continues from where interrupted
--retry-failed: resets FAILED → PENDING before running
"""

from __future__ import annotations

import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from pipeline.state_manager import StateManager
from neper.tessellation    import run_tessellation, TessellationConfig
from neper.visualization   import run_visualization, VisualizationConfig
from utils.logger          import get_logger
from utils.paths           import ensure_dir
log = get_logger(__name__)


def run_neper_stage(
    dataset:         object,         # pd.DataFrame
    dataset_dir:     str | Path,
    tess_cfg:        TessellationConfig,
    vis_cfg:         VisualizationConfig,
    state:           StateManager,
    n_workers:       int  = 4,
    dry_run:         bool = False,
    retry_failed:    bool = False,
) -> dict:
    """
    Run Neper tessellation for all samples in a dataset.

    Parameters
    ----------
    dataset      : pd.DataFrame  — one row per sample, columns = parameter names
    dataset_dir  : Path          — N_<n> folder
    tess_cfg     : TessellationConfig
    vis_cfg      : VisualizationConfig
    state        : StateManager  — shared checkpoint
    n_workers    : int           — parallel Neper processes
    dry_run      : bool          — build commands but do not execute
    retry_failed : bool          — reset FAILED → PENDING before running

    Returns
    -------
    dict  {"done": int, "failed": int, "skipped": int}
    """
    dataset_dir = Path(dataset_dir)

    if retry_failed:
        n_reset = state.reset_failed("neper")
        log.info("Retry mode: reset %d FAILED → PENDING (neper)", n_reset)

    sample_ids = state.pending_ids("neper")
    log.info("Neper stage: %d samples pending  (workers=%d  dry_run=%s)",
             len(sample_ids), n_workers, dry_run)

    if not sample_ids:
        log.info("Nothing to do for neper stage.")
        return {"done": 0, "failed": 0, "skipped": 0}

    results = {"done": 0, "failed": 0, "skipped": 0}

    t0 = time.perf_counter()

    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(
                _neper_worker,
                sample_id  = sid,
                sample_row = dataset.iloc[sid],
                dataset_dir= dataset_dir,
                tess_cfg   = tess_cfg,
                vis_cfg    = vis_cfg,
                dry_run    = dry_run,
            ): sid
            for sid in sample_ids
        }

        for future in as_completed(futures):
            sid = futures[future]
            try:
                outcome = future.result()
                state.set_status(sid, "neper", outcome)
                results[outcome.lower() if outcome != "DONE" else "done"] = results.get(outcome.lower() if outcome != "DONE" else "done", 0) + 1
                if outcome == "DONE":
                    results["done"] += 1
                elif outcome == "FAILED":
                    results["failed"] += 1
            except Exception as exc:
                log.error("Neper worker raised for sample %04d: %s", sid, exc)
                state.set_status(sid, "neper", "FAILED")
                results["failed"] += 1
    
    elapsed = time.perf_counter() - t0
    log.info("Neper stage wall time: %.2f s (%.2f min)", elapsed, elapsed / 60.0)
    
    state.print_summary()
    results["elapsed_s"] = elapsed
    return results


def _neper_worker(
    sample_id:   int,
    sample_row:  object,
    dataset_dir: Path,
    tess_cfg:    TessellationConfig,
    vis_cfg:     VisualizationConfig,
    dry_run:     bool,
) -> str:
    """Single-sample Neper worker (runs in a subprocess)."""
    sample_dir = ensure_dir(dataset_dir / f"sample_{sample_id:04d}")
    
    os.environ["OMP_NUM_THREADS"] = "1"  # Neper uses OpenMP; limit to 1 thread per process to avoid oversubscription when running multiple processes in parallel.
    
    try:
        tess_result = run_tessellation(
            sample_row = sample_row,
            sample_id  = sample_id,
            sample_dir = sample_dir,
            cfg        = tess_cfg,
            dry_run    = dry_run,
        )
        tess_file = tess_result.get("tess_file")
        if tess_file:
            run_visualization(
                tess_file  = tess_file,
                sample_id  = sample_id,
                sample_dir = sample_dir,
                cfg        = vis_cfg,
                dry_run    = dry_run,
            )
        return "DONE"
    except Exception:
        log.error("Neper FAILED sample %04d:\n%s", sample_id, traceback.format_exc())
        return "FAILED"
