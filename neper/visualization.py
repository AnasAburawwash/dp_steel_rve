"""
neper/visualization.py
Build and execute the neper -V command for RVE visualization and QC.

Role in the pipeline
---------------------
neper -V is run AFTER -T on the .tess and .tesr files to produce:
  1. PNG slice images of the RVE  (quality check, paper figures)
  2. IPF colour maps per phase    (texture verification)
  3. Grain size distribution PNG  (validates lognormal morpho)

These images are NOT required for DAMASK — they are QC artefacts only.
Visualization is therefore OPTIONAL per sample and is controlled by
pipeline_config.yaml:  visualization: {enabled: true, n_samples: 5}
meaning only the first n_samples tessellations are visualized (sufficient
for a paper Methods figure).

neper -V command structure
--------------------------
neper -V <tess_file>
    -datacellcol "group"            ← colour by phase (group 1=ferrite, 2=martensite)
    -datacellcolscheme "red,blue"   ← ferrite=red, martensite=blue
    -cameraangle 15
    -imagesize 800:800
    -imageformat png
    -O <output_stem>

For grain size distribution (from .stcell statistics):
    neper -V <tess_file>
    -datacellcol "diameq"
    -datacellcolscheme "jet"
    -colorbaraxis "on"
    -O <output_stem>_diameq

References
----------
Quey, R. et al., Comput. Methods Appl. Mech. Eng. 200 (2011) 1729-1745.
Neper 4.10.1 documentation: https://neper.info/doc/neper_v.html
"""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, field

from utils.paths  import to_wsl_path, ensure_dir
from utils.logger import get_logger
from core.exceptions import NeperError

log = get_logger(__name__)


# ── Visualization configuration ───────────────────────────────────────────────

@dataclass
class VisualizationConfig:
    """
    Parameters for neper -V rendering.

    Parameters
    ----------
    enabled          : bool
        Master switch. If False, run_visualization() returns immediately.
    auto_n           : int
        During pipeline execution, automatically visualize the first auto_n
        samples (0 to auto_n-1). Keeps overhead low. Default: 5.
    sample_ids       : list[int]
        Explicit list of sample IDs to visualize, regardless of auto_n.
        Used for on-demand rendering of any specific sample after the pipeline.
        Example: [0, 42, 137, 999]
        If non-empty, auto_n is ignored for those IDs.
    image_size       : str
        Image resolution as "WxH" pixels (neper format: "800:800").
    camera_angle     : float
        Camera field-of-view angle in degrees (default 15 = parallel projection).
    phase_colours    : list[str]
        Colour per group index. Index 0 = Ferrite, index 1 = Martensite.
        Uses X11/CSS colour names supported by neper.
    render_diameq    : bool
        If True, also produce a grain-size colourmap image.
    render_ipf       : bool
        If True, produce an IPF (inverse pole figure) orientation colour map.
        Requires neper compiled with the visualization option.
    neper_executable : str
        Path or name of the neper executable.
    timeout_s        : int
        Subprocess timeout in seconds (default 120 per render pass).
    """
    enabled:          bool      = True
    auto_n:           int       = 5
    sample_ids:       list      = field(default_factory=list)
    image_size:       str       = "800:800"
    camera_angle:     float     = 15.0
    phase_colours:    list      = field(default_factory=lambda: ["red", "royalblue"])
    render_diameq:    bool      = True
    render_ipf:       bool      = False
    neper_executable: str       = "neper"
    timeout_s:        int       = 120


# ── Public entry point ────────────────────────────────────────────────────────

def run_visualization(
    tess_file:  Path,
    sample_id:  int,
    sample_dir: Path,
    cfg:        VisualizationConfig,
    dry_run:    bool = False,
) -> dict:
    """
    Run neper -V on a completed tessellation to produce QC PNG images.

    Parameters
    ----------
    tess_file  : Path
        Path to the .tess file produced by run_tessellation().
    sample_id  : int
        Zero-based sample index (used for log messages and skip logic).
    sample_dir : Path
        Root directory for this sample — visualizations go to sample_dir/neper/.
    cfg        : VisualizationConfig
    dry_run    : bool
        If True, build and log commands but do not execute.

    Returns
    -------
    dict with keys:
        phase_png    : Path or None   — phase colour map image
        diameq_png   : Path or None   — grain size colour map image
        ipf_png      : Path or None   — IPF colour map image
        elapsed_s    : float
        skipped      : bool           — True if cfg.enabled=False or n > n_samples
    """
    # ── Early exit ────────────────────────────────────────────────────────────
    if not cfg.enabled:
        log.debug("Visualization disabled (cfg.enabled=False). Skipping sample %04d.", sample_id)
        return _skipped_result()

    # Render if: explicitly listed in cfg.sample_ids  OR  within auto_n range
    explicitly_requested = sample_id in cfg.sample_ids
    within_auto_range    = sample_id < cfg.auto_n
    if not explicitly_requested and not within_auto_range:
        log.debug(
            "Visualization skipped: sample_id=%04d not in sample_ids and "
            ">= auto_n=%d.", sample_id, cfg.auto_n,
        )
        return _skipped_result()

    if not tess_file.exists() and not dry_run:
        log.warning("Tess file not found: %s. Skipping visualization.", tess_file)
        return _skipped_result()

    neper_dir   = ensure_dir(sample_dir / "neper")
    output_stem = neper_dir / f"sample_{sample_id:04d}"

    t0      = time.perf_counter()
    results = {}

    # ── Pass 1: phase colour map ──────────────────────────────────────────────
    phase_png = output_stem.with_name(f"sample_{sample_id:04d}_phase.png")
    cmd_phase = _build_phase_cmd(tess_file, output_stem, cfg)
    _execute(cmd_phase, phase_png, sample_id, cfg, dry_run, "phase")
    results["phase_png"] = phase_png if (dry_run or phase_png.exists()) else None

    # ── Pass 2: grain size (diameq) colour map ────────────────────────────────
    diameq_png = None
    if cfg.render_diameq:
        diameq_stem = output_stem.with_name(f"sample_{sample_id:04d}_diameq")
        diameq_png  = diameq_stem.with_suffix(".png")
        cmd_diameq  = _build_diameq_cmd(tess_file, diameq_stem, cfg)
        _execute(cmd_diameq, diameq_png, sample_id, cfg, dry_run, "diameq")
        results["diameq_png"] = diameq_png if (dry_run or diameq_png.exists()) else None
    else:
        results["diameq_png"] = None

    # ── Pass 3: IPF colour map (optional, expensive) ─────────────────────────
    ipf_png = None
    if cfg.render_ipf:
        ipf_stem = output_stem.with_name(f"sample_{sample_id:04d}_ipf")
        ipf_png  = ipf_stem.with_suffix(".png")
        cmd_ipf  = _build_ipf_cmd(tess_file, ipf_stem, cfg)
        _execute(cmd_ipf, ipf_png, sample_id, cfg, dry_run, "IPF")
        results["ipf_png"] = ipf_png if (dry_run or ipf_png.exists()) else None
    else:
        results["ipf_png"] = None

    elapsed = time.perf_counter() - t0
    log.info("Visualization complete  sample_id=%04d  elapsed=%.1fs", sample_id, elapsed)

    return {
        **results,
        "elapsed_s": elapsed,
        "skipped":   False,
    }


# ── Command builders ──────────────────────────────────────────────────────────

def _build_phase_cmd(
    tess_file: Path,
    output_stem: Path,
    cfg: VisualizationConfig,
) -> list[str]:
    """
    Build the neper -V command for a phase-coloured RVE image.

    Colour assignment:
        Group 1 (Ferrite)    → cfg.phase_colours[0]  (default: red)
        Group 2 (Martensite) → cfg.phase_colours[1]  (default: royalblue)

    The -datacellcol "group" option colours each grain by its group ID.
    -datacellcolscheme maps group IDs to colours using a comma-separated list.
    """
    colour_scheme = ",".join(cfg.phase_colours)

    return [
        cfg.neper_executable, "-V",
        to_wsl_path(tess_file),
        "-datacellcol",       "group",
        "-datacellcolscheme", colour_scheme,
        "-cameraangle",       str(cfg.camera_angle),
        "-imagesize",         cfg.image_size,
        "-imageformat",       "png",
        "-O",                 to_wsl_path(output_stem) + "_phase",
    ]


def _build_diameq_cmd(
    tess_file: Path,
    output_stem: Path,
    cfg: VisualizationConfig,
) -> list[str]:
    """
    Build the neper -V command for a grain-size (diameq) colour map.

    Uses a continuous "blue→white→red" diverging colourmap.
    The colour bar axis is shown for quantitative reading.
    This image is used to verify that the lognormal morpho distribution
    was reproduced correctly by the Laguerre tessellation.
    """
    return [
        cfg.neper_executable, "-V",
        to_wsl_path(tess_file),
        "-datacellcol",       "diameq",
        "-datacellcolscheme", "blue,white,red",
        "-datacelltrs",       "0.0",
        "-cameraangle",       str(cfg.camera_angle),
        "-imagesize",         cfg.image_size,
        "-imageformat",       "png",
        "-colorbaraxis",      "on",
        "-O",                 to_wsl_path(output_stem),
    ]


def _build_ipf_cmd(
    tess_file: Path,
    output_stem: Path,
    cfg: VisualizationConfig,
) -> list[str]:
    """
    Build the neper -V command for an IPF (inverse pole figure) orientation map.

    Orientation colour coding:
        -datacellcol "ori"           uses Euler angles stored in the .tess file
        -datacellcolscheme "ipf"     maps orientations to RGB via standard IPF
        -crysym "cI"                 BCC cubic symmetry (required for IPF)

    This image shows the crystallographic texture of the RVE.
    For a random texture (as generated), the IPF should show uniform colour
    distribution. Any clustering indicates a texture bias.
    """
    return [
        cfg.neper_executable, "-V",
        to_wsl_path(tess_file),
        "-datacellcol",       "ori",
        "-datacellcolscheme", "ipf",
        "-crysym",            "cI",
        "-cameraangle",       str(cfg.camera_angle),
        "-imagesize",         cfg.image_size,
        "-imageformat",       "png",
        "-O",                 to_wsl_path(output_stem),
    ]


# ── Execution helper ──────────────────────────────────────────────────────────

def _execute(
    cmd:        list[str],
    output_png: Path,
    sample_id:  int,
    cfg:        VisualizationConfig,
    dry_run:    bool,
    pass_name:  str,
) -> None:
    """Execute one neper -V pass. Logs but does NOT raise on failure."""
    log.debug("neper -V [%s] command: %s", pass_name, " ".join(cmd))

    if dry_run:
        log.info("DRY RUN [%s] — command not executed.", pass_name)
        return

    log_file = output_png.parent / f"neper_vis_{pass_name}.log"
    try:
        result = subprocess.run(
            cmd,
            cwd=str(output_png.parent),
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            timeout=cfg.timeout_s,
            check=False,
        )
        if result.returncode != 0:
            log.warning(
                "neper -V [%s] exited with code %d (sample %04d). "
                "See %s. Continuing pipeline.",
                pass_name, result.returncode, sample_id, log_file,
            )
        elif not output_png.exists():
            log.warning(
                "neper -V [%s] succeeded (rc=0) but PNG not found: %s",
                pass_name, output_png,
            )
        else:
            log.debug("neper -V [%s] OK — %s", pass_name, output_png.name)

    except subprocess.TimeoutExpired:
        log.warning(
            "neper -V [%s] timed out after %ds (sample %04d). Continuing.",
            pass_name, cfg.timeout_s, sample_id,
        )
    except FileNotFoundError:
        log.error(
            "neper executable not found: '%s'. "
            "Check neper_executable in pipeline_config.yaml.",
            cfg.neper_executable,
        )


# ── Helper ────────────────────────────────────────────────────────────────────

def _skipped_result() -> dict:
    return {
        "phase_png":  None,
        "diameq_png": None,
        "ipf_png":    None,
        "elapsed_s":  0.0,
        "skipped":    True,
    }


# ── Standalone / on-demand entry point ───────────────────────────────────────

def render_sample(
    sample_dir:   "Path",
    sample_id:    int,
    cfg:          "VisualizationConfig | None" = None,
    render_ipf:   bool = False,
    dry_run:      bool = False,
) -> dict:
    """
    Render any specific sample on demand, without modifying the pipeline config.

    Convenience wrapper around run_visualization() — useful for interactive
    inspection of a sample after the pipeline has completed, or for generating
    paper figures for a specific sample.

    Parameters
    ----------
    sample_dir  : Path
        Root directory for this sample (e.g. N_500/sample_0042/).
        The .tess file is expected at sample_dir/neper/sample_XXXX.tess.
    sample_id   : int
        Zero-based sample index.
    cfg         : VisualizationConfig or None
        If None, a default config is used with enabled=True, auto_n=0
        (so the sample_ids list is the only gate).
    render_ipf  : bool
        Override cfg.render_ipf for this call. Default False.
    dry_run     : bool
        If True, build and log commands but do not execute.

    Returns
    -------
    dict — same structure as run_visualization().

    Example
    -------
        from neper.visualization import render_sample
        result = render_sample(
            sample_dir = Path("E:/PhD/cp_projects/N_500/sample_0042"),
            sample_id  = 42,
        )
        print(result["phase_png"])
    """
    from pathlib import Path as _Path

    if cfg is None:
        cfg = VisualizationConfig(
            enabled      = True,
            auto_n       = 0,           # disable auto range
            sample_ids   = [sample_id], # explicit: render only this one
            render_diameq= True,
            render_ipf   = render_ipf,
        )
    else:
        # Clone with updated sample_ids to include this sample
        import dataclasses
        cfg = dataclasses.replace(
            cfg,
            enabled    = True,
            auto_n     = max(cfg.auto_n, 0),
            sample_ids = list(set(cfg.sample_ids) | {sample_id}),
            render_ipf = render_ipf or cfg.render_ipf,
        )

    tess_file = (
        _Path(sample_dir) / "neper" / f"sample_{sample_id:04d}.tess"
    )
    return run_visualization(
        tess_file  = tess_file,
        sample_id  = sample_id,
        sample_dir = _Path(sample_dir),
        cfg        = cfg,
        dry_run    = dry_run,
    )
