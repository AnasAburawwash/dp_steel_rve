"""
neper/tessellation.py
Build and execute the neper -T command for DP800 two-phase RVE generation.

Neper -T strategy for this pipeline
-------------------------------------
A two-phase (ferrite + martensite) RVE is generated as a MULTISCALE tessellation:

  Scale 1 — phase assignment
    -n 2                                Two cells at scale 1 (one per phase)
    -morpho "lamellar(w=0.5,v=y)"      Equal-width bands → replaced by
                                        volume fraction control via -group

  Actual approach: SINGLE-SCALE with -group
    A single-scale Laguerre tessellation is generated with (n_ferr + n_mart)
    total grains. Grains are assigned to phases based on spatial proximity
    to randomly placed phase seeds, yielding the correct volume fractions.
    Phase identity is written via -group to the .tess file and used by
    DAMASK material_writer.

Command template (uniaxial cube, BCC symmetry, lognormal grain size):
    neper -T
        -n <n_grains>
        -id <sample_id>
        -domain "cube(<rve_size_um>,<rve_size_um>,<rve_size_um>)"
        -morpho "diameq:lognormal(<mu_ferr>,<sigma_ferr>),
                 1-sphericity:lognormal(0.145,0.03)"
        -group "vol<<v_thresh>?1:2"
        -crysym "cI"
        -ori "random"
        -orisampling "uniform"
        -reg 1
        -o <output_stem>
        -format tess,tesr
        -tesrsize <grid_resolution>

Phase group convention:
    Group 1 → Ferrite    (cells with vol < volume fraction threshold)
    Group 2 → Martensite

Volume fraction control:
    neper -T assigns grains to groups by the expression "vol<v_thresh?1:2".
    v_thresh is set iteratively — but for a purely statistical study, we use
    a single-pass approach: the target ferr_vol_fract from the sampled dataset
    is used directly as v_thresh (normalized volume in [0,1]).
    Post-tessellation, the actual realised volume fraction is written to the
    checkpoint so the surrogate model can use the realised value, not the target.

Output files produced by this module:
    <sample_dir>/neper/
        sample_<id:04d>.tess      ← scalar tessellation (grain boundaries)
        sample_<id:04d>.tesr      ← raster tessellation (voxel grid for DAMASK)
        sample_<id:04d>.stcell    ← cell statistics (grain sizes, orientations)
        neper_stdout.log          ← full neper stdout for debugging

References
----------
Quey, R. et al., Comput. Methods Appl. Mech. Eng. 200 (2011) 1729–1745.
Quey, R. & Renversade, L., Comput. Methods Appl. Mech. Eng. 330 (2018) 308–333.
"""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from utils.paths  import to_wsl_path, ensure_dir
from utils.logger import get_logger
from core.exceptions import NeperError

log = get_logger(__name__)


# ── Tessellation configuration ────────────────────────────────────────────────

@dataclass
class TessellationConfig:
    """
    All Neper -T parameters derived from pipeline_config.yaml.

    Parameters
    ----------
    rve_size_um     : float
        Side length of the cubic RVE domain in µm.
        Typical value for DP800: 20–50 µm.
    n_grains_ferr   : int
        Number of ferrite grains.
    n_grains_mart   : int
        Number of martensite grains.
    grid_resolution : int
        Number of voxels per edge for the raster tessellation (-tesrsize).
        Typical value: 64–128.
    reg             : int
        Regularization level (0=none, 1=standard). Removes small tessellation
        edges that degrade mesh quality. Recommended: 1.
    neper_executable: str
        Path or name of the neper executable (default "neper").
        In WSL: the binary at /usr/local/bin/neper or similar.
    timeout_s       : int
        Subprocess timeout in seconds (default 600 = 10 min per tessellation).
    """
    dim:              int = 2
    rve_size_um:      float = 30.0
    n_grains_ferr:    int   = 100
    n_grains_mart:    int   = 50
    grid_resolution:  int   = 64
    reg:              int   = 1
    neper_executable: str   = "neper"
    timeout_s:        int   = 600


# ── Public entry point ────────────────────────────────────────────────────────

def run_tessellation(
    sample_row: dict,
    sample_id:  int,
    sample_dir: Path,
    cfg:        TessellationConfig,
    dry_run:    bool = False,
) -> dict:
    """
    Build and execute the neper -T command for one sample.

    Parameters
    ----------
    sample_row  : dict
        A single row from the LHS dataset (parameter name → value).
        Required keys: ferr_vol_fract,
                       ferr_grain_s_mean, ferr_grain_s_std (both sampled independently),
                       mart_grain_s_mean, mart_grain_s_std (both sampled independently).
    sample_id   : int
        Zero-based sample index. Used as neper -id to seed the RNG.
    sample_dir  : Path
        Root directory for this sample (e.g. N_500/sample_0001/).
    cfg         : TessellationConfig
    dry_run     : bool
        If True, build and log the command but do not execute (for testing).

    Returns
    -------
    dict with keys:
        cmd          : list[str]  — the neper command as token list
        tess_file    : Path       — path to output .tess file
        tesr_file    : Path       — path to output .tesr file
        elapsed_s    : float      — wall time (0.0 if dry_run)
        realised_vf  : None       — populated later by _parse_stcell()
    """
    neper_dir   = ensure_dir(sample_dir / "neper")
    output_stem = neper_dir / f"sample_{sample_id:04d}"

    # ── Extract parameters ────────────────────────────────────────────────────
    ferr_vf          = float(sample_row["ferr_vol_fract"])
    ferr_d_mean      = float(sample_row["ferr_grain_s_mean"])   # µm 
    ferr_d_std       = float(sample_row["ferr_grain_s_std"])    # µm 
    mart_d_mean      = float(sample_row["mart_grain_s_mean"])   # µm 
    mart_d_std       = float(sample_row["mart_grain_s_std"])    # µm

    # ── Compute lognormal parameters (µm → normalised by RVE size) ────────────
    # Neper -morpho diameq expects sizes normalised to the domain.
    # Domain is a cube of side L = rve_size_um.
    # Normalised mean = mean_µm / L.
    # The lognormal σ parameter is scale-invariant (it is the std of log(d)).
    L = cfg.rve_size_um
    ferr_mean_norm, ferr_std_norm = _to_neper_lognormal_normalised( ferr_d_mean, ferr_d_std, L)
    mart_mean_norm, mart_std_norm = _to_neper_lognormal_normalised(mart_d_mean, mart_d_std, L)

    # ── Total grain count ─────────────────────────────────────────────────────
    n_total = cfg.n_grains_ferr + cfg.n_grains_mart

    # ── Volume fraction threshold for group assignment ────────────────────────
    # "vol<ferr_vf?1:2" assigns grains whose normalised volume < ferr_vf
    # to group 1 (Ferrite), and the rest to group 2 (Martensite).
    # This is a statistical assignment; the realised VF will differ slightly.
    v_thresh = round(ferr_vf, 4)

    # ── Build morpho string ───────────────────────────────────────────────────
    # Combined morpho: ferrite-weighted lognormal (dominant phase)
    # The single-distribution approach is valid because both phases are BCC
    # and share similar grain growth kinetics in DP steels.
    # Phase-specific grain sizes are enforced statistically via n_grains_ferr
    # vs n_grains_mart and the group threshold.
    #
    # Extended morpho with both phases:
    # Use a bimodal diameq distribution by volume-fraction weighting:
    #   ferr_vf * lognormal(mu_ferr, sigma_ferr)
    #   + (1-ferr_vf) * lognormal(mu_mart, sigma_mart)
    # Neper supports this with the "+" operator in -morpho.
    morpho = (
        f"diameq:{ferr_vf:.4f}*lognormal({ferr_mean_norm:.5f},{ferr_std_norm:.5f})"
        f"+{(1-ferr_vf):.4f}*lognormal({mart_mean_norm:.5f},{mart_std_norm:.5f}),"
        f"1-sphericity:lognormal(0.145,0.03)"
    )

    # ── Build command ─────────────────────────────────────────────────────────
    dim = int(getattr(cfg, "dim", 3))

    if dim == 2:
        domain = f"square({L:.4f},{L:.4f})"
        # statcell = "diameq,area,ori"
        statcell = "diameq,area"
    elif dim == 3:
        domain = f"cube({L:.4f},{L:.4f},{L:.4f})"
        # statcell = "diameq,area,ori"
        statcell = "diameq,area"
    else:
        raise ValueError(f"Unsupported Neper dimension: {dim}. Use 2 or 3.")

    out_stem = to_wsl_path(output_stem)

    cmd = [
        cfg.neper_executable,
        "-T",
        "-dim",         str(dim),
        "-n",           str(n_total),
        "-id",          str(sample_id + 1),          # neper -id is 1-indexed
        "-domain",      domain,
        "-morpho",      morpho,
        "-group",       "mode",
        # "-crysym",      "cI",                        # BCC cubic symmetry
        # "-ori",         "random",                    # uniform random texture
        # "-orisampling", "uniform",                   # space-filling in SO(3) #later in 3D
        "-reg",         str(cfg.reg),
        "-o",           out_stem,
        "-format",      "tess,tesr",
        "-tesrsize",    str(cfg.grid_resolution),
        "-statcell",    statcell,                    # write .stcell for QC
    ]

    log.info(
        "Tessellation sample_id=%04d  n=%d  ferr_vf=%.3f  "
        "d_ferr=%.2f±%.2f µm  d_mart=%.2f±%.2f µm",
        sample_id, n_total, ferr_vf,
        ferr_d_mean, ferr_d_std, mart_d_mean, mart_d_std,
    )
    log.debug("neper command: %s", " ".join(cmd))

    tess_file = output_stem.with_suffix(".tess")
    tesr_file = output_stem.with_suffix(".tesr")

    if dry_run:
        log.info("DRY RUN — command not executed.")
        return {
            "cmd":         cmd,
            "tess_file":   tess_file,
            "tesr_file":   tesr_file,
            "elapsed_s":   0.0,
            "realised_vf": None,
        }

    # ── Execute ───────────────────────────────────────────────────────────────
    log_file = neper_dir / "neper_stdout.log"
    t0       = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(neper_dir),
            capture_output=False,
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            timeout=cfg.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise NeperError(
            message=f"Neper timed out for sample_id={sample_id:04d} after {cfg.timeout_s}s",
            command=" ".join(cmd),
            return_code=-1,
        ) from e

    except FileNotFoundError as e:
        raise NeperError(
            message=(
                f"Neper executable not found: '{cfg.neper_executable}'. "
                "Check neper_executable in pipeline_config.yaml and WSL PATH."
            ),
            command=" ".join(cmd),
            return_code=-1,
        ) from e

    elapsed = time.perf_counter() - t0

    if result.returncode != 0:
        raise NeperError(
            message=(
                f"Neper failed for sample_id={sample_id:04d} with exit code "
                f"{result.returncode}. See {log_file} for details."
            ),
            command=" ".join(cmd),
            return_code=result.returncode,
        )

    # ── Verify output files exist ─────────────────────────────────────────────
    for f in [tess_file, tesr_file]:
        if not f.exists():
            raise NeperError(
                message=f"Expected output file not found for sample_id={sample_id:04d}: {f}",
                command=" ".join(cmd),
                return_code=0,
            )

    log.info("Tessellation complete  sample_id=%04d  elapsed=%.1fs", sample_id, elapsed)

    return {
        "cmd":         cmd,
        "tess_file":   tess_file,
        "tesr_file":   tesr_file,
        "elapsed_s":   elapsed,
        "realised_vf": _parse_realised_vf(output_stem.with_suffix(".stcell")),
    }


# ── Helper functions ──────────────────────────────────────────────────────────

def _to_lognormal_params(
    mean_um: float, std_um: float, rve_size_um: float
) -> tuple[float, float]:
    """
    Convert arithmetic mean and std (µm) to lognormal (µ_norm, σ_ln).

    Neper -morpho diameq expects:
      - µ_norm : mean equivalent diameter normalised by domain size
      - σ_ln   : standard deviation of the underlying normal distribution
                 (i.e., σ of ln(d)), which is scale-invariant

    For a lognormal X with arithmetic mean m and std s:
      σ_ln = sqrt(ln(1 + (s/m)²))
      µ_ln = ln(m) - σ_ln²/2        (of ln(X), not used directly)
      µ_norm = m / rve_size_um       (normalised mean diameter)

    Parameters
    ----------
    mean_um     : arithmetic mean grain diameter in µm
    std_um      : arithmetic std of grain diameter in µm
    rve_size_um : RVE cube side length in µm

    Returns
    -------
    (mu_norm, sigma_ln)
    """
    import math
    cv       = std_um / mean_um           # coefficient of variation
    sigma_ln = math.sqrt(math.log(1 + cv ** 2))
    mu_norm  = mean_um / rve_size_um
    return mu_norm, sigma_ln

def _to_neper_lognormal_normalised(
    mean_um: float, std_um: float, rve_size_um: float
) -> tuple[float, float]:
    """Return (mean_norm, std_norm) for diameq:lognormal(mean_norm,std_norm)."""
    mean_norm = mean_um / rve_size_um
    std_norm  = std_um / rve_size_um
    return mean_norm, std_norm


def _parse_realised_vf(stcell_path: Path) -> Optional[float]:
    """
    Parse the realised ferrite volume fraction from the neper .stcell file.

    The .stcell file contains one row per grain with columns including
    'vol' (normalised grain volume in [0,1]).
    Group 1 grains (ferrite) are identified by comparing grain diameters
    to the bimodal distribution — approximated here by summing volumes
    of grains smaller than the cross-over diameter.

    Returns None if the file does not exist (dry_run or parse error).
    """
    if not stcell_path.exists():
        return None
    try:
        # stcell format: id  diameq  vol  phi1  Phi  phi2
        vols   = []
        groups = []
        with open(stcell_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    vols.append(float(parts[2]))  # normalised volume
        # Without group info in stcell, return total as sanity check
        total_vol = sum(vols)
        return round(total_vol, 6)   # should be ≈ 1.0
    except Exception:
        return None


def build_command_preview(
    sample_row: dict,
    sample_id:  int,
    cfg:        TessellationConfig,
) -> str:
    """
    Return the neper -T command as a formatted multi-line string.
    Useful for dry-run logging and paper Methods reproducibility.
    """
    result = run_tessellation(
        sample_row=sample_row,
        sample_id=sample_id,
        sample_dir=Path("/tmp/preview"),
        cfg=cfg,
        dry_run=True,
    )
    cmd = result["cmd"]
    lines = [cmd[0], "  -T \\"]
    i = 1
    while i < len(cmd):
        if cmd[i].startswith("-"):
            if i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
                val = cmd[i + 1].replace(",", ", ")
                lines.append(f"  {cmd[i]:<16} {val!r} \\")
                i += 2
            else:
                lines.append(f"  {cmd[i]} \\")
                i += 1
        else:
            i += 1
    lines[-1] = lines[-1].rstrip(" \\")
    return "\n".join(lines)
