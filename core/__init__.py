"""
core — shared data structures, exceptions, and parameter contracts.

Public API
----------
Exceptions (all inherit from DPSteelError)
    DPSteelError                Base for all pipeline errors
    ParameterValidationError    Invalid ParameterSchema definition
    PhysicalConstraintError     Sample violates physical constraint (C11<C12 etc.)
    SamplingError               LHS sampling failure / NaN / inf
    NeperError                  Neper command failure (+ .command, .return_code)
    DAMASKError                 DAMASK failure (+ .sample_id, .return_code)
    ConfigurationError          Missing / invalid keys in pipeline_config.yaml
    CheckpointError             State file corrupted or unreadable

Parameter schema
    ParameterSchema             Dataclass describing one CP parameter
    ParameterBounds             NamedTuple (low, high) — compatibility alias

Constraints
    check_martensite_fraction   Volume-fraction consistency guard
    check_parameter_bounds      Raises SamplingError if any sample is out of bounds
    check_elastic_consistency   Born stability criteria for cubic elastic constants
"""

from core.exceptions import (
    DPSteelError,
    ParameterValidationError,
    PhysicalConstraintError,
    SamplingError,
    NeperError,
    DAMASKError,
    ConfigurationError,
    CheckpointError,
)
from core.parameter_schema import ParameterSchema, ParameterBounds
from core.constraints import (
    check_martensite_fraction,
    check_parameter_bounds,
    check_elastic_consistency,
)

__all__ = [
    # exceptions
    "DPSteelError",
    "ParameterValidationError",
    "PhysicalConstraintError",
    "SamplingError",
    "NeperError",
    "DAMASKError",
    "ConfigurationError",
    "CheckpointError",
    # schema
    "ParameterSchema",
    "ParameterBounds",
    # constraints
    "check_martensite_fraction",
    "check_parameter_bounds",
    "check_elastic_consistency",
]
