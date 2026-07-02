"""
pipeline/runner.py
Top-level orchestrator: runs the full pipeline for one dataset size N.

Called by main.py once per N value (50, 100, ..., 1000).

Sequence
--------
1. dataset_builder.build_dataset()   → load or generate LHS samples
2. StateManager(dataset_dir, N)      → load or init checkpoint
3. neper_runner.run_neper_stage()    → tessellate all samples
4. damask_runner.run_damask_stage()  → simulate all samples

Each stage is resumable: interrupted samples are detected from the checkpoint
and re-queued automatically.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.state_manager    import StateManager
from pipeline.dataset_builder  import build_dataset
from pipeline.neper_runner     import run_neper_stage
from pipeline.damask_runner    import run_damask_stage
from neper.tessellation        import TessellationConfig
from neper.visualization       import VisualizationConfig
from utils.logger              import get_logger

log = get_logger(__name__)


def run_pipeline_for_n(
    n_samples:         int,
    base_dir:          str | Path,
    data_dir:          str | Path,
    all_params:        list,
    cfg:               dict,          # parsed pipeline_config.yaml
    stage:             str  = "all",  # "neper" | "damask" | "all"
    dry_run:           bool = False,
    retry_failed:      bool = False,
    force_regen:       bool = False,
    batch_index:  int  | None = None,   # 1-based LSF array index
    batch_size:   int         = 50,     # samples per job array task
) -> None:
    """
    Run the full pipeline (or a single stage) for one dataset size.

    Parameters
    ----------
    n_samples    : int
    base_dir     : Path — root project folder (e.g. E:/PhD/cp_projects)
    data_dir     : Path — where dataset .data files live
    all_params   : list[ParameterSchema]
    cfg          : dict parsed from pipeline_config.yaml
    damask_module: the imported `damask` Python package
    stage        : which stages to run ("all" | "neper" | "damask")
    dry_run      : bool
    retry_failed : bool
    force_regen  : bool — regenerate LHS dataset even if file exists
    batch_index  : int | None — 1-based LSF array index
    batch_size   : int — samples per job array task
    """
    dataset_dir = Path(base_dir) / f"N_{n_samples}"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Pipeline  N=%d  stage=%s  dry_run=%s", n_samples, stage, dry_run)
    log.info("=" * 60)

    # ── 1. Dataset ─────────────────────────────────────────────────────────
    dataset = build_dataset(
        n_samples   = n_samples,
        data_dir    = data_dir,
        all_params  = all_params,
        seed        = cfg.get("seed", 42),
        force_regen = force_regen,
        export_csv  = True,
    )
    assert len(dataset) == n_samples, f"Dataset length mismatch: {len(dataset)} != {n_samples}"

    # ── Batch slice (job-array mode) ───────────────────────────────────────
    if batch_index is not None:
        idx_start = (batch_index - 1) * batch_size          # 0-based start
        idx_end   = min(idx_start + batch_size, n_samples)  # exclusive end

        if idx_start >= n_samples:
            log.warning(
                "Batch index %d is out of range for N=%d (batch_size=%d). Nothing to do.",
                batch_index, n_samples, batch_size,
            )
            return

        dataset   = dataset.iloc[idx_start:idx_end]         # preserves original index labels
        batch_ids = set(dataset.index.tolist())              # e.g. {0,1} or {2,3}

        log.info(
            "Batch mode: index=%d  samples %d–%d  (%d samples)",
            batch_index, idx_start, idx_end - 1, len(dataset),
        )
    else:
        batch_ids = None    # no filter — run all samples (local / single-job mode)

    # ── 2. State ───────────────────────────────────────────────────────────
    state = StateManager(dataset_dir, n_samples)
    # StateManager is always initialised for the FULL N.
    # This ensures all tasks share one checkpoint file per dataset folder,
    # and sample IDs in the state match the global 0..N-1 indexing.

    # ── 3. Neper stage ─────────────────────────────────────────────────────
    if stage in ("all", "neper"):
        neper_cfg  = cfg.get("neper", {})
        vis_cfg_d  = cfg.get("visualization", {})
        tess_cfg   = TessellationConfig(
            dim                = neper_cfg.get("dim", 2),
            n_grains_ferr      = neper_cfg.get("n_grains_ferr", 300),
            n_grains_mart      = neper_cfg.get("n_grains_mart", 100),
            rve_size_um        = neper_cfg.get("rve_length_um", 50.0),
            neper_executable   = neper_cfg.get("executable", "neper"),
            timeout_s          = neper_cfg.get("timeout_s", 600),
        )
        vis_cfg = VisualizationConfig(
            enabled            = vis_cfg_d.get("enabled", True),
            auto_n             = vis_cfg_d.get("auto_n", 5),
            sample_ids         = vis_cfg_d.get("sample_ids", []),
            render_diameq      = vis_cfg_d.get("render_diameq", True),
            render_ipf         = vis_cfg_d.get("render_ipf", False),
            neper_executable   = neper_cfg.get("executable", "neper"),
        )
        run_neper_stage(
            dataset      = dataset,
            dataset_dir  = dataset_dir,
            tess_cfg     = tess_cfg,
            vis_cfg      = vis_cfg,
            state        = state,
            n_workers    = cfg.get("neper", {}).get("n_workers", 4),
            dry_run      = dry_run,
            retry_failed = retry_failed,
            batch_ids    = batch_ids,
        )

    # ── 4. DAMASK stage ────────────────────────────────────────────────────
    if stage in ("all", "damask"):
        d_cfg = cfg.get("damask", {})
        rve_size_m = np.array(d_cfg.get("rve_size_m", [50e-6, 50e-6, 50e-6]))
        run_damask_stage(
            dataset            = dataset,
            dataset_dir        = dataset_dir,
            state              = state,
            rve_size_m         = rve_size_m,
            damask_executable  = d_cfg.get("executable", "DAMASK_grid"),
            n_threads          = d_cfg.get("n_threads", 4),
            n_workers          = d_cfg.get("n_workers", 1),
            timeout_s          = d_cfg.get("timeout_s", 3600),
            dry_run            = dry_run,
            retry_failed       = retry_failed,
            batch_ids    = batch_ids,
        )
