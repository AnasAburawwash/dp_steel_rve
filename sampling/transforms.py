"""
sampling/transforms.py
Per-parameter LHS → physical value transforms.

Two transforms are used in this pipeline:

  transform_uniform(u, min_val, max_val)
      u ∈ (0,1)  →  linear mapping to [min_val, max_val]
      Used for: elastic constants, CRSS, hardening params, n_sl, a_sl,
                volume fraction.

  transform_log_uniform(u, min_val, max_val)
      u ∈ (0,1)  →  10^(log10(min) + u·(log10(max)-log10(min)))
      Used for: grain size (spans ~1 decade), axial_strain_rate (3 decades).
      Correct when the physical response scales with log(parameter).

Why NOT norm.ppf + MinMaxScaler (original approach):
  - norm.ppf(0) = -inf, norm.ppf(1) = +inf → NaN/inf at LHS boundaries
  - MinMaxScaler applied AFTER ppf distorts the space-filling property of LHS
  - Bounded parameters have no physical justification for normal tails
"""

import numpy as np


def transform_uniform(u: np.ndarray, min_val: float, max_val: float) -> np.ndarray:
    """
    Linear transform from LHS unit hypercube to [min_val, max_val].

    Parameters
    ----------
    u        : 1-D array of LHS samples in (0, 1)
    min_val  : lower bound of the parameter range
    max_val  : upper bound of the parameter range

    Returns
    -------
    np.ndarray of physical parameter values in [min_val, max_val]
    """
    u = np.clip(u, 1e-9, 1 - 1e-9)
    return min_val + u * (max_val - min_val)


def transform_log_uniform(u: np.ndarray, min_val: float, max_val: float) -> np.ndarray:
    """
    Log-uniform transform from LHS unit hypercube.
    Correct for parameters whose physical effect scales with log(value).

    Parameters
    ----------
    u        : 1-D array of LHS samples in (0, 1)
    min_val  : lower bound  (must be > 0)
    max_val  : upper bound  (must be > min_val)

    Returns
    -------
    np.ndarray of physical values log-uniformly distributed in [min_val, max_val]
    """
    if min_val <= 0:
        raise ValueError(f"transform_log_uniform requires min_val > 0, got {min_val}")
    u = np.clip(u, 1e-9, 1 - 1e-9)
    log_min = np.log10(min_val)
    log_max = np.log10(max_val)
    return 10.0 ** (log_min + u * (log_max - log_min))


def transform(u: np.ndarray, param) -> np.ndarray:
    """
    Dispatch to the correct transform based on param.distribution.

    Parameters
    ----------
    u     : 1-D array of LHS samples in (0, 1)
    param : ParameterSchema instance

    Returns
    -------
    np.ndarray of physical parameter values
    """
    if param.distribution == "log":
        return transform_log_uniform(u, param.min_val, param.max_val)
    elif param.distribution == "uniform":
        return transform_uniform(u, param.min_val, param.max_val)
    else:
        raise ValueError(
            f"Unknown distribution '{param.distribution}' for parameter '{param.name}'. "
            f"Supported: 'uniform', 'log'."
        )
