"""
damask/load_writer.py
Create the DAMASK load-case YAML for uniaxial tension using sampled axial strain rate.

Uses damask.LoadcaseGrid for proper serialization and the inversion() helper to
guarantee dot_F / P masks are always perfectly complementary.
"""

from pathlib import Path
import damask


def inversion(l, fill=0):
    """Invert a nested list mask: 'x' → fill, anything else → 'x'."""
    return [
        inversion(i, fill) if isinstance(i, list)
        else fill if i == 'x'
        else 'x'
        for i in l
    ]


def build_uniaxial_tension_load(
    axial_strain_rate: float,
    total_time: float = 180.0,
    n_increments: int = 100,
) -> damask.LoadcaseGrid:

    axial_strain_rate = float(axial_strain_rate)

    dot_F = [
        [axial_strain_rate, 0.0,  0.0],
        [0.0,               'x',  0.0],
        [0.0,               0.0,  'x'],
    ]

    loadstep = {
        'boundary_conditions': {
            'mechanical': {
                'dot_F': dot_F,
                'P':     inversion(dot_F),   # auto-complementary mask
            }
        },
        'discretization': {'t': float(total_time), 'N': int(n_increments)},
        'f_out': 1,
    }

    load_case = damask.LoadcaseGrid(
        solver={'mechanical': 'spectral_polarization'},
        loadstep=[loadstep],
    )
    return load_case


def write_load_yaml(
    sample_row,
    sample_dir: str | Path,
    filename: str = 'tensionX.yaml',
) -> Path:
    sample_dir = Path(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)

    load_case = build_uniaxial_tension_load(sample_row['axial_strain_rate'])

    out_path = sample_dir / filename
    load_case.save(str(out_path))
    return out_path