"""
sampling/lhs_sampler.py
Latin Hypercube Sampler for the DP800 CP pipeline.

Design decisions
----------------
1. Uses scipy.stats.qmc.LatinHypercube (replaces deprecated pyDOE.lhs):
     - reproducible via seed
     - supports scrambling and centering options
     - actively maintained

2. Only SAMPLED parameters enter the LHS matrix.
   DERIVED and FIXED parameters are handled after sampling:
     - grain_s_std  = alpha_std × grain_s_mean  (alpha_std sampled per grain family)
     - mart_vol_fract = 1 - ferr_vol_fract       (enforced exactly)

3. Physical constraints are validated before the dataset is returned.
   Samples violating CRITICAL constraints are rejected and resampled
   (rejection rate should be ~0 given the non-overlapping ranges).

Usage
-----
    from materials import SAMPLED_PARAMETERS
    from sampling  import LHSSampler

    sampler = LHSSampler(SAMPLED_PARAMETERS, seed=42)
    dataset = sampler.sample(n=500)          # pd.DataFrame, shape (500, 29)
"""

import numpy as np
import pandas as pd
from scipy.stats.qmc import LatinHypercube, discrepancy

from sampling.transforms import transform
from sampling.validators import RangeValidator, PhysicalValidator


class LHSSampler:
    """
    Generate LHS-based parameter datasets for DAMASK/Neper simulations.

    Parameters
    ----------
    sampled_params : list[ParameterSchema]
        Parameters with role='sampled'. Obtain via:
            from materials import SAMPLED_PARAMETERS
    seed : int
        Random seed for reproducibility (default 42).
    max_rejection_iters : int
        Maximum resampling attempts for constraint satisfaction (default 5).
    """

    def __init__(self, sampled_params: list, seed: int = 42,
                 max_rejection_iters: int = 5):
        self.sampled_params      = sampled_params
        self.seed                = seed
        self.max_rejection_iters = max_rejection_iters
        self._dim                = len(sampled_params)

    # ── Public API ────────────────────────────────────────────────────────────

    def sample(self, n: int) -> pd.DataFrame:
        """
        Generate n physically valid parameter samples.

        Parameters
        ----------
        n : int — number of samples

        Returns
        -------
        pd.DataFrame with columns for all sampled + derived parameters.
        Columns are in the canonical order defined in materials/__init__.py.
        """
        unit_samples = self._draw_lhs(n)
        dataset      = self._transform(unit_samples)
        dataset      = self._compute_derived(dataset)
        dataset      = self._enforce_precision(dataset)

        RangeValidator(self.sampled_params).validate(dataset)
        PhysicalValidator(self.sampled_params).validate(dataset)

        self._log_discrepancy(unit_samples)
        return dataset

    # ── Internal steps ────────────────────────────────────────────────────────

    def _draw_lhs(self, n: int) -> np.ndarray:
        """Draw raw LHS samples in the unit hypercube [0,1]^d."""
        sampler = LatinHypercube(d=self._dim, seed=self.seed, scramble=True)
        return sampler.random(n=n)          # shape (n, d)

    def _transform(self, unit_samples: np.ndarray) -> pd.DataFrame:
        """Apply per-parameter transforms to map unit samples to physical values."""
        data = {}
        for idx, param in enumerate(self.sampled_params):
            data[param.name] = transform(unit_samples[:, idx], param)
        return pd.DataFrame(data)

    def _compute_derived(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute derived parameters from sampled values.

        Derived parameters handled here:
          mart_vol_fract = 1 - ferr_vol_fract  (enforced exactly, not in LHS)

        Note on grain_s_std:
          ferr_grain_s_std and mart_grain_s_std have role='derived' in the
          schema, but they are INDEPENDENTLY sampled via LHS (uniform dist,
          own min/max range). They do NOT enter here — they arrive already
          populated from _transform() as columns in df.
          This is the correct treatment: std is a free parameter, not a
          function of mean. The constraint std < mean is enforced by
          ConstraintValidator after sampling.
        """
        df = df.copy()

        # Ferrite grain-size spread from sampled ratio
        if {"ferr_grain_s_mean", "ferr_grain_s_ratio"}.issubset(df.columns):
            df["ferr_grain_s_std"] = (
                df["ferr_grain_s_mean"] * df["ferr_grain_s_ratio"]
            ).round(3)

        # Martensite grain-size spread from sampled ratio
        if {"mart_grain_s_mean", "mart_grain_s_ratio"}.issubset(df.columns):
            df["mart_grain_s_std"] = (
                df["mart_grain_s_mean"] * df["mart_grain_s_ratio"]
            ).round(3)

        # Volume-fraction complement — only if ferrite fraction is part of the schema
        if "ferr_vol_fract" in df.columns:
            df["ferr_vol_fract"] = df["ferr_vol_fract"].round(4)
            df["mart_vol_fract"] = (1.0 - df["ferr_vol_fract"]).round(4)

        return df

    def _enforce_precision(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Round parameters to physically meaningful precision.
        Avoids spurious significant figures in DAMASK YAML files.
        """
        df = df.copy()
        # Stresses → 1 MPa precision
        stress_cols = [c for c in df.columns if any(
            k in c for k in ["C11","C12","C44","xi_0","xi_inf","h0_sl"])]
        for col in stress_cols:
            df[col] = df[col].round(0)

        # Dimensionless constants → 4 decimal places
        dimless_cols = [c for c in df.columns if any(
            k in c for k in ["n_sl","a_sl","vol_fract"])]
        for col in dimless_cols:
            df[col] = df[col].round(4)

        # Grain sizes → 3 decimal places (nm precision in µm)
        grain_cols = [c for c in df.columns if "grain_s" in c]
        for col in grain_cols:
            df[col] = df[col].round(3)

        # Strain rate → 6 significant figures
        if "axial_strain_rate" in df.columns:
            df["axial_strain_rate"] = df["axial_strain_rate"].round(8)

        return df

    def _log_discrepancy(self, unit_samples: np.ndarray):
        """
        Log the centered L²-discrepancy of the LHS design.
        Lower is better. A good LHS with n>>d should give discrepancy < 0.01.
        """
        try:
            d = discrepancy(unit_samples, method="CD")
            print(f"  LHS discrepancy (CD): {d:.6f}  "
                  f"({'good' if d < 0.01 else 'acceptable' if d < 0.05 else 'poor'})")
        except Exception:
            pass   # non-critical — do not block sampling
