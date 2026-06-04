"""core/constraints.py — physical constraint guards for sampled parameters."""

import pandas as pd
from core.exceptions import SamplingError, PhysicalConstraintError


def check_martensite_fraction(
    df,
    col:  str   = "f_martensite",
    low:  float = 0.10,
    high: float = 0.40,
) -> None:
    """Raise SamplingError if martensite volume fraction is outside [low, high]."""
    if col not in df.columns:
        return
    out = df[(df[col] < low) | (df[col] > high)]
    if not out.empty:
        raise SamplingError(
            f"{len(out)} sample(s) have {col} outside [{low}, {high}]: "
            f"indices {out.index.tolist()}"
        )


def check_parameter_bounds(df, schemas: list) -> None:
    """
    Raise SamplingError if any sample violates its ParameterSchema bounds.

    Works with your ParameterSchema design (min_val / max_val attributes).
    """
    violations = []
    for schema in schemas:
        if schema.name not in df.columns:
            continue
        col = df[schema.name]
        bad = df[(col < schema.min_val) | (col > schema.max_val)]
        if not bad.empty:
            violations.append(
                f"  {schema.name}: {len(bad)} sample(s) outside "
                f"[{schema.min_val}, {schema.max_val}]"
            )
    if violations:
        raise SamplingError(
            "Parameter bound violations:\n" + "\n".join(violations)
        )


def check_elastic_consistency(
    C11: float, C12: float, C44: float, phase: str = "unknown"
) -> None:
    """
    Raise PhysicalConstraintError if cubic elastic constants violate
    Born stability criteria: C11 > C12, C11 + 2*C12 > 0, C44 > 0.
    """
    if C11 <= C12:
        raise PhysicalConstraintError(
            f"{phase}: C11 ({C11:.3e}) must be > C12 ({C12:.3e})",
            constraint_name="C11_gt_C12", severity="critical",
        )
    if C11 + 2 * C12 <= 0:
        raise PhysicalConstraintError(
            f"{phase}: C11 + 2*C12 = {C11 + 2*C12:.3e} must be > 0",
            constraint_name="bulk_modulus_positive", severity="critical",
        )
    if C44 <= 0:
        raise PhysicalConstraintError(
            f"{phase}: C44 ({C44:.3e}) must be > 0",
            constraint_name="C44_positive", severity="critical",
        )
