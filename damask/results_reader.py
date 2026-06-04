"""
damask/results_reader.py
Thin wrapper for reading DAMASK HDF5 results.

Left intentionally lightweight for now: it exposes one helper to open the output file path,
keeping post-processing decoupled from simulation orchestration.
"""

from pathlib import Path
import h5py


def open_result_file(sample_dir: str | Path, filename: str | None = None):
    sample_dir = Path(sample_dir)
    if filename is None:
        candidates = sorted(sample_dir.glob('*.hdf5')) + sorted(sample_dir.glob('*.h5'))
        if not candidates:
            raise FileNotFoundError(f'No DAMASK result file found in {sample_dir}')
        filename = candidates[0]
    return h5py.File(filename, 'r')