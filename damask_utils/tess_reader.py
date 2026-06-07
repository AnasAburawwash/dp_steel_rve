"""
damask/tess_reader.py
Parse Neper .tess files to recover grain-wise phase assignment and orientations.

Why this module exists
----------------------
DAMASK material entries must be added in the same grain/material order as the geometry
material indices. Using GeomGrid.load_Neper(...).renumber() produces contiguous material
indices, while the .tess file preserves grain-wise metadata like group and orientation [web:143].
This parser keeps the grain order intact so grain i always receives orientation i and phase i.
"""

from dataclasses import dataclass
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class TessData:
    n_grains: int
    phase_idxs: list[int]
    rodrigues_neper: np.ndarray

    @property
    def rodrigues_damask(self) -> np.ndarray:
        """
        Convert Neper 3-component Rodrigues vectors [r1, r2, r3]
        (where magnitude = tan(theta/2)) to DAMASK's 4-component
        Rodrigues-Frank form [n1, n2, n3, tan(theta/2)], with sign flip
        for active->passive convention.
        """
        ro3 = self.rodrigues_neper          # shape (N, 3)
        norms = np.linalg.norm(ro3, axis=1, keepdims=True)  # shape (N, 1)

        # Avoid division by zero for zero-rotation grains
        safe_norms = np.where(norms < 1e-10, 1.0, norms)
        unit_axes = ro3 / safe_norms        # shape (N, 3), unit vectors

        # Passive convention: negate axes (equivalent to negating the 3-vector)
        unit_axes_passive = -unit_axes

        # tan(theta/2) is the magnitude; zero-rotation grains get 0.0
        tan_half = np.where(norms[:, 0] < 1e-10, 0.0, norms[:, 0])  # shape (N,)

        return np.column_stack([unit_axes_passive, tan_half])  # shape (N, 4)


def parse_tess(file_path: str | Path) -> TessData:
    file_path = Path(file_path)
    lines = file_path.read_text(encoding='utf-8', errors='ignore').splitlines()

    n_grains = _parse_n_grains(lines)
    phase_idxs = _parse_group_block(lines, n_grains)
    rodrigues = _parse_ori_block(lines, n_grains)

    if len(phase_idxs) != n_grains:
        raise ValueError(f'Expected {n_grains} phase ids, got {len(phase_idxs)}')
    if rodrigues.shape != (n_grains, 3):
        raise ValueError(f'Expected Rodrigues array shape {(n_grains, 3)}, got {rodrigues.shape}')

    tess = TessData(n_grains=n_grains, phase_idxs=phase_idxs, rodrigues_neper=rodrigues)

    # ── Sanity check: verify rodrigues_damask conversion ──────────────────
    ro4 = tess.rodrigues_damask                              # (N, 4)
    assert ro4.shape == (n_grains, 4), f'Expected (N,4), got {ro4.shape}'
    axis_norms = np.linalg.norm(ro4[:, :3], axis=1)
    non_identity = ro4[:, 3] > 1e-10
    assert np.allclose(axis_norms[non_identity], 1.0, atol=1e-6), \
        f'Non-unit rotation axes found; max deviation: {np.abs(axis_norms[non_identity] - 1.0).max():.2e}'
    # ──────────────────────────────────────────────────────────────────────

    return tess

def _parse_n_grains(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        s = line.strip()
        if s == '**cell':
            for j in range(i + 1, min(i + 6, len(lines))):
                cand = lines[j].strip()
                if cand.isdigit():
                    return int(cand)
    raise ValueError('Could not determine n_grains from **cell block')


def _parse_group_block(lines: list[str], n_grains: int) -> list[int]:
    values = []
    in_group = False
    for line in lines:
        s = line.strip()
        if s == '*group':
            in_group = True
            continue
        if in_group and s.startswith('*'):
            break
        if in_group and s:
            values.extend(int(x) for x in s.split())
            if len(values) >= n_grains:
                return values[:n_grains]
    raise ValueError('Could not parse *group block from .tess')


def _parse_ori_block(lines: list[str], n_grains: int) -> np.ndarray:
    rows = []
    in_ori = False
    for line in lines:
        s = line.strip()
        if s == '*ori':
            in_ori = True
            continue
        if in_ori and s.startswith('descriptor'):
            continue
        if in_ori and s.startswith('*'):
            break
        if in_ori and s:
            parts = s.split()
            if len(parts) >= 3:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2])])
                if len(rows) >= n_grains:
                    return np.asarray(rows[:n_grains], dtype=float)
    raise ValueError('Could not parse *ori block from .tess')
