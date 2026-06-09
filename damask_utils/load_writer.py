"""
damask/load_writer.py
Create the DAMASK load-case YAML for uniaxial tension using sampled axial strain rate.
total_time and N_increments are derived from the sampled strain rate so that
every sample gets an appropriate time discretisation.
"""

from __future__ import annotations
from pathlib import Path
import damask


# ── Physics constants ─────────────────────────────────────────────────────────
TARGET_STRAIN   = 0.20          # 20 % axial engineering strain
MIN_INCREMENTS  = 100           # never fewer than 100 steps
DT_MIN          = 0.05          # minimum time per increment (s) — avoids ~0-length steps
DT_MAX          = 2.0           # maximum time per increment (s) — keeps it well-resolved


def inversion(l, fill=0):
    """Invert a nested list mask: 'x' → fill, anything else → 'x'."""
    return [
        inversion(i, fill) if isinstance(i, list)
        else fill if i == 'x'
        else 'x'
        for i in l
    ]


def compute_loadcase_timing(
    axial_strain_rate: float,
    target_strain: float = TARGET_STRAIN,
    min_increments: int  = MIN_INCREMENTS,
    dt_min: float        = DT_MIN,
    dt_max: float        = DT_MAX,
) -> tuple[float, int]:
    """
    Derive (total_time, n_increments) that are consistent with the sampled
    strain rate, so the solver always sees an appropriate time step size.

    Strategy
    --------
    1. total_time  = target_strain / axial_strain_rate
    2. n_increments chosen so dt = total_time / N stays within [dt_min, dt_max]
       and is at least min_increments.

    Returns
    -------
    total_time   : float  — simulation duration in seconds
    n_increments : int    — number of load increments
    """
    total_time = target_strain / axial_strain_rate          # e.g. 0.20 / 1e-3 = 200 s

    # Lower bound: never fewer than min_increments
    n_from_min  = min_increments

    # Upper bound on dt → lower bound on N
    n_from_dt_max = int(total_time / dt_max) + 1            # N ≥ total_time / dt_max

    # Lower bound on dt → upper bound on N (avoid tiny steps that blow HPC walltime)
    n_from_dt_min = int(total_time / dt_min)                # N ≤ total_time / dt_min

    n_increments = max(n_from_min, n_from_dt_max)
    n_increments = min(n_increments, n_from_dt_min)         # cap at dt_min floor
    n_increments = max(n_increments, 1)                     # absolute safety

    return float(total_time), int(n_increments)


def build_uniaxial_tension_load(
    axial_strain_rate: float,
    total_time: float | None  = None,
    n_increments: int | None  = None,
    target_strain: float      = TARGET_STRAIN,
) -> damask.LoadcaseGrid:
    """
    Build a uniaxial tension loadcase.

    If total_time / n_increments are not supplied they are computed
    adaptively from axial_strain_rate via compute_loadcase_timing().
    Pass them explicitly only when you need to override (e.g. restart).
    """
    axial_strain_rate = float(axial_strain_rate)

    if total_time is None or n_increments is None:
        total_time, n_increments = compute_loadcase_timing(
            axial_strain_rate, target_strain=target_strain
        )

    dot_F = [
        [axial_strain_rate, 0.0,  0.0],
        [0.0,               'x',  0.0],
        [0.0,               0.0,  'x'],
    ]

    loadstep = {
        'boundary_conditions': {
            'mechanical': {
                'dot_F': dot_F,
                'P':     inversion(dot_F),
            }
        },
        'discretization': {'t': float(total_time), 'N': int(n_increments)},
        'f_out': 1,
    }

    return damask.LoadcaseGrid(
        solver={'mechanical': 'spectral_polarization'},
        loadstep=[loadstep],
    )


def write_load_yaml(
    sample_row,
    sample_dir: str | Path,
    filename: str = 'tensionX.yaml',
) -> Path:
    sample_dir = Path(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)

    load_case = build_uniaxial_tension_load(
        axial_strain_rate=sample_row['axial_strain_rate'],
        # total_time and n_increments intentionally omitted → adaptive
    )

    out_path = sample_dir / filename
    load_case.save(str(out_path))
    return out_path