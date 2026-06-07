"""
damask/grid_builder.py
Build DAMASK geometry from Neper output using GeomGrid.load_Neper().

GeomGrid.load_Neper() reads Neper geometry output and renumber() maps material indices
to a contiguous 0..N-1 range, which is the required material ordering contract for DAMASK [web:143].
"""

from pathlib import Path
import numpy as np
import damask


def build_geom_from_neper(sample_dir: str | Path, rve_size_m) -> Path:
    sample_dir = Path(sample_dir)
    neper_dir = sample_dir / 'neper'
    vtk_candidates = sorted(neper_dir.glob('*.vtk')) + sorted(neper_dir.glob('*.vti'))
    if not vtk_candidates:
        raise FileNotFoundError(f'No Neper grid file found in {neper_dir}')
    grid_file = vtk_candidates[0]

    geom = damask.GeomGrid.load_Neper(str(grid_file)).renumber()
    geom.size = np.asarray(rve_size_m, dtype=float)

    out_path = sample_dir / f'{sample_dir.name}.vti'
    geom.save(str(out_path))
    return out_path