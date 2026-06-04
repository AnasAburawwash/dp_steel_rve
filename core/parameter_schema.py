"""
core/parameter_schema.py
ParameterSchema dataclass — the single source of truth for every
material or loading parameter in the pipeline.

Design principles:
  - Immutable after construction (frozen=True)
  - All domain knowledge (units, DAMASK keys, roles) lives here
  - Validated at construction via __post_init__

Compatibility note
------------------
ParameterBounds is provided as a NamedTuple alias so that existing
materials/*.py files that call ParameterBounds(low, high) continue to
work. It is not used internally by ParameterSchema (which uses
min_val / max_val directly).
"""

from dataclasses import dataclass, field
from typing import Literal, NamedTuple
from core.exceptions import ParameterValidationError


# ── Compatibility alias (used by materials/*.py) ───────────────────────────
class ParameterBounds(NamedTuple):
    """Simple (low, high) range container — kept for backward compatibility."""
    low:  float
    high: float


# Type aliases for clarity
Role         = Literal["independent", "dependent", "derived", "fixed", "loading"]
Distribution = Literal["uniform", "log", "norm"]
ParamType    = Literal["stress", "rate", "length", "constant", "ratio", "angle"]


@dataclass(frozen=True)
class ParameterSchema:
    """
    Complete description of a single material or loading parameter.

    Attributes
    ----------
    name : str
        Unique code key used as DataFrame column name.
        Convention: {phase_prefix}_{damask_key}  e.g. 'ferr_C_11'

    physical_name : str
        Human-readable description for plots and paper tables.
        e.g. 'Elastic stiffness C11 (Ferrite)'

    latex_symbol : str
        LaTeX symbol for axis labels and paper equations.
        e.g. r'$C_{11}^{\\alpha}$'

    damask_key : str
        Exact key used in DAMASK material.yaml.
        e.g. 'C_11'  Maps directly to DAMASK constitutive parameter names.

    phase : str
        Phase this parameter belongs to.
        e.g. 'Ferrite', 'Martensite', 'Global'

    reference : float
        Nominal/calibrated reference value (literature or experimental).
        Must satisfy min_val <= reference <= max_val for non-fixed params.

    min_val : float
        Lower bound of the sampling range.

    max_val : float
        Upper bound of the sampling range.

    unit : str
        Physical unit as stored in the dataset. e.g. 'MPa', 's-1', 'um', '-'

    damask_unit : str
        Physical unit expected by DAMASK. May differ from unit.
        e.g. unit='MPa', damask_unit='Pa' → unit_factor=1e6

    unit_factor : float
        Multiplicative factor: damask_value = dataset_value * unit_factor
        Default 1.0 (no conversion needed).

    role : Role
        Sampling role:
        - 'independent' : freely sampled via LHS
        - 'dependent'   : computed from one other parameter (e.g. std = f(mean))
        - 'derived'     : computed from multiple parameters (e.g. grain_size_std = mean * ratio)
        - 'fixed'       : constant at reference value across all samples
        - 'loading'     : loading condition, sampled independently (strain rate etc.)

    distribution : Distribution
        Sampling distribution for LHS transform:
        - 'uniform' : linear mapping  val = min + u*(max-min)
        - 'log'     : log-uniform     val = 10^(log10(min) + u*(log10(max)-log10(min)))
        - 'norm'    : normal          val = norm.ppf(u, loc=mean, scale=std)

    param_type : ParamType
        Physical type — used for grouping in sensitivity plots and tables.

    constraint_group : str
        Optional group name linking parameters that share a physical constraint.
        e.g. 'xi_ferr_sl1' links 'ferr_xi_0_sl_1' and 'ferr_xi_inf_sl_1'
        Empty string means no cross-parameter constraint.

    notes : str
        Optional documentation string. Appears in auto-generated parameter tables.
    """

    # Identity
    name:             str
    physical_name:    str
    latex_symbol:     str
    damask_key:       str
    phase:            str

    # Range
    reference:        float
    min_val:          float
    max_val:          float

    # Units
    unit:             str
    damask_unit:      str          = field(default="")
    unit_factor:      float        = field(default=1.0)

    # Sampling
    role:             Role         = field(default="independent")
    distribution:     Distribution = field(default="uniform")

    # Metadata
    param_type:       ParamType    = field(default="constant")
    constraint_group: str          = field(default="")
    notes:            str          = field(default="")

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if not self.name.strip():
            raise ParameterValidationError("Parameter name cannot be empty.")
        if self.min_val > self.max_val:
            raise ParameterValidationError(
                f"[{self.name}] min_val ({self.min_val}) > max_val ({self.max_val}). "
                f"Range is inverted."
            )
        if self.role in ("independent", "loading"):
            if not (self.min_val <= self.reference <= self.max_val):
                raise ParameterValidationError(
                    f"[{self.name}] reference ({self.reference}) is outside "
                    f"[{self.min_val}, {self.max_val}]."
                )
        if self.distribution == "log" and self.min_val <= 0:
            raise ParameterValidationError(
                f"[{self.name}] distribution='log' requires min_val > 0, "
                f"got min_val={self.min_val}."
            )
        if self.unit_factor <= 0:
            raise ParameterValidationError(
                f"[{self.name}] unit_factor must be positive, got {self.unit_factor}."
            )

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def is_sampled(self) -> bool:
        """True if this parameter enters LHS sampling directly."""
        return self.role in ("independent", "loading")

    @property
    def is_computed(self) -> bool:
        """True if this parameter is computed from others, not sampled."""
        return self.role in ("dependent", "derived")

    @property
    def needs_unit_conversion(self) -> bool:
        """True if DAMASK expects a different unit than the dataset stores."""
        return self.unit_factor != 1.0

    @property
    def damask_reference(self) -> float:
        """Reference value converted to DAMASK units."""
        return self.reference * self.unit_factor

    def __repr__(self) -> str:
        return (
            f"ParameterSchema("
            f"name='{self.name}', "
            f"role='{self.role}', "
            f"range=[{self.min_val}, {self.max_val}] {self.unit}, "
            f"dist='{self.distribution}')"
        )

    def summary_row(self) -> dict:
        """Returns a dict suitable for a summary DataFrame or paper table."""
        return {
            "Parameter":     self.name,
            "Physical Name": self.physical_name,
            "Symbol":        self.latex_symbol,
            "Phase":         self.phase,
            "Reference":     self.reference,
            "Min":           self.min_val,
            "Max":           self.max_val,
            "Unit":          self.unit,
            "Role":          self.role,
            "Distribution":  self.distribution,
            "Type":          self.param_type,
        }
