"""
damask/solver.py
Run a DAMASK spectral simulation for one sample directory.
"""

from pathlib import Path
import os
import subprocess
import time

from core.exceptions import DAMASKError


def run_solver(sample_dir: str | Path, executable: str = 'DAMASK_grid', n_threads: int = 1, timeout_s: int = 3600) -> dict:
    sample_dir = Path(sample_dir)
    env = os.environ.copy()
    env['OMP_NUM_THREADS'] = str(int(n_threads))

    cmd = [
        executable,
        '--geom', str(sample_dir / f'{sample_dir.name}.vti'),
        '--load', str(sample_dir / 'tensionX.yaml'),
        '--material', str(sample_dir / 'material.yaml'),
    ]

    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, cwd=str(sample_dir), env=env, timeout=timeout_s, capture_output=True, text=True, check=False)
    except subprocess.TimeoutExpired as e:
        raise DAMASKError(message='DAMASK solver timed out', sample_id=sample_dir.name) from e
    except FileNotFoundError as e:
        raise DAMASKError(message=f'DAMASK executable not found: {executable}', sample_id=sample_dir.name) from e

    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        raise DAMASKError(message=result.stderr[-2000:], sample_id=sample_dir.name, return_code=result.returncode)

    return {'elapsed_s': elapsed, 'return_code': result.returncode, 'stdout_tail': result.stdout[-1000:]}
