"""
sampling/validators.py
Two-layer validation for the sampling pipeline.

Layer 1 — RangeValidator
    Checks every sampled column stays within [min_val, max_val] as defined
    in the ParameterSchema. Catches transform bugs or schema edits that
    accidentally push samples outside physical bounds.

Layer 2 — ConstraintValidator
    Runs the full core.constraints registry against the dataset.
    Separates critical violations (reject) from warnings (log and keep).
    Returns a clean dataset and a validation report.

Usage (called automatically by LHSSampler, but can be used standalone):
    from sampling.validators import RangeValidator, ConstraintValidator

    rv = RangeValidator(all_parameters)
    rv.validate(df)                          # raises SamplingError on failure

    cv = ConstraintValidator(CONSTRAINTS)
    clean_df, report = cv.validate(df)       # returns filtered df + report
"""

import pandas as pd
from core.exceptions import SamplingError

from core.constraints import (
    check_parameter_bounds,
    check_martensite_fraction,
    check_elastic_consistency,
)
from core.exceptions import SamplingError, PhysicalConstraintError

class RangeValidator:
    """
    Validates that every sampled column lies within its schema-defined range.

    Parameters
    ----------
    parameters : list[ParameterSchema]
        All parameters (any role). Only role='independent' columns are checked.
    rtol : float
        Relative tolerance for boundary checks (default 1e-6).
        Accounts for floating-point rounding in transforms.
    """

    def __init__(self, parameters: list, rtol: float = 1e-6):
        self.params = {p.name: p for p in parameters if p.role == "independent"}
        self.rtol   = rtol

    def validate(self, df: pd.DataFrame) -> None:
        """
        Check all sampled columns are within [min_val, max_val].

        Raises
        ------
        SamplingError
            If any column has out-of-range values, with a detailed report.
        """
        violations = []
        for col, param in self.params.items():
            if col not in df.columns:
                continue
            tol  = self.rtol * (param.max_val - param.min_val)
            lo   = df[col] < (param.min_val - tol)
            hi   = df[col] > (param.max_val + tol)
            n_lo = int(lo.sum())
            n_hi = int(hi.sum())
            if n_lo > 0 or n_hi > 0:
                violations.append(
                    f"  {col}: {n_lo} below min ({param.min_val}) | "
                    f"{n_hi} above max ({param.max_val})"
                )

        if violations:
            msg = "Range validation failed:\n" + "\n".join(violations)
            raise SamplingError(msg)

    def report(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Return a DataFrame summarising range coverage for all sampled columns.
        Useful for verifying space-filling quality.
        """
        rows = []
        for col, param in self.params.items():
            if col not in df.columns:
                continue
            rows.append({
                "parameter":   col,
                "schema_min":  param.min_val,
                "schema_max":  param.max_val,
                "sample_min":  df[col].min(),
                "sample_max":  df[col].max(),
                "coverage_%":  round(
                    100 * (df[col].max() - df[col].min())
                    / (param.max_val - param.min_val), 1
                ),
            })
        return pd.DataFrame(rows)


class PhysicalValidator:
    """
    Runs physical consistency checks on a sampled dataset.

    Uses the function-based checks defined in core/constraints.py.
    Critical violations raise SamplingError with offending sample IDs.
    """

    def __init__(self, parameters: list):
        self.parameters = parameters

    def validate(self, df: pd.DataFrame) -> None:
        # 1) Schema-level bounds on all columns present
        check_parameter_bounds(df, self.parameters)

        # 2) Optional martensite fraction check
        if "mart_vol_fract" in df.columns:
            check_martensite_fraction(
                df,
                col="mart_vol_fract",
                low=0.08,
                high=0.50,
            )

        # 3) Ferrite cubic elastic stability
        ferr_cols = {"ferr_C11", "ferr_C12", "ferr_C44"}
        if ferr_cols.issubset(df.columns):
            bad_rows = []
            for idx, row in df[list(ferr_cols)].iterrows():
                try:
                    check_elastic_consistency(
                        C11=float(row["ferr_C11"]),
                        C12=float(row["ferr_C12"]),
                        C44=float(row["ferr_C44"]),
                        phase="ferrite",
                    )
                except PhysicalConstraintError as e:
                    bad_rows.append((idx, e.constraint_name, str(e)))

            if bad_rows:
                msg = "Ferrite elastic stability violated:\n" + "\n".join(
                    f"  sample {idx}: [{name}] {text}"
                    for idx, name, text in bad_rows[:20]
                )
                if len(bad_rows) > 20:
                    msg += f"\n  ... and {len(bad_rows)-20} more"
                raise SamplingError(msg)

        # 4) Martensite cubic elastic stability
        mart_cols = {"mart_C11", "mart_C12", "mart_C44"}
        if mart_cols.issubset(df.columns):
            bad_rows = []
            for idx, row in df[list(mart_cols)].iterrows():
                try:
                    check_elastic_consistency(
                        C11=float(row["mart_C11"]),
                        C12=float(row["mart_C12"]),
                        C44=float(row["mart_C44"]),
                        phase="martensite",
                    )
                except PhysicalConstraintError as e:
                    bad_rows.append((idx, e.constraint_name, str(e)))

            if bad_rows:
                msg = "Martensite elastic stability violated:\n" + "\n".join(
                    f"  sample {idx}: [{name}] {text}"
                    for idx, name, text in bad_rows[:20]
                )
                if len(bad_rows) > 20:
                    msg += f"\n  ... and {len(bad_rows)-20} more"
                raise SamplingError(msg)
