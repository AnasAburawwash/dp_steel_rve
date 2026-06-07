"""
damask/interaction_matrix.py
Build the 24-entry BCC slip interaction vector h_sl-sl for DAMASK phenopowerlaw.

Design
------
For the current DP-steel workflow, we keep the simple 2-parameter interaction model:
- h_aa: self/coplanar hardening factor
- h_ab: latent/cross hardening factor

DAMASK's phenopowerlaw expects h_sl-sl as a flattened interaction vector whose length
matches the slip-system family interaction definition for the chosen lattice/slip setup [web:141].
This module keeps the mapping explicit and testable.
"""

from dataclasses import dataclass

SELF_INDICES_24 = {0, 2}
VECTOR_LENGTH = 24


@dataclass(frozen=True)
class InteractionMatrixSpec:
    self_indices: set = None
    vector_length: int = VECTOR_LENGTH

    def __post_init__(self):
        object.__setattr__(self, 'self_indices', SELF_INDICES_24 if self.self_indices is None else set(self.self_indices))
        if self.vector_length <= 0:
            raise ValueError('vector_length must be positive')
        if not self.self_indices:
            raise ValueError('self_indices cannot be empty')
        if min(self.self_indices) < 0 or max(self.self_indices) >= self.vector_length:
            raise ValueError('self_indices out of bounds')


def build_h_sl_sl(h_aa: float, h_ab: float, spec: InteractionMatrixSpec | None = None) -> list[float]:
    """
    Build DAMASK phenopowerlaw h_sl-sl vector for BCC 12+12 slip families.

    Parameters
    ----------
    h_aa : float
        Self/coplanar hardening factor.
    h_ab : float
        Latent/cross hardening factor.
    spec : InteractionMatrixSpec | None
        Optional override for testing or future models.

    Returns
    -------
    list[float]
        Length-24 interaction vector.
    """
    spec = spec or InteractionMatrixSpec()
    h_aa = float(h_aa)
    h_ab = float(h_ab)
    return [h_aa if i in spec.self_indices else h_ab for i in range(spec.vector_length)]
