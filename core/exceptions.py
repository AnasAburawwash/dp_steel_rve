"""
core/exceptions.py
Custom exceptions for the DP Steel RVE pipeline.
All pipeline errors inherit from DPSteelError for easy top-level catching.
"""


class DPSteelError(Exception):
    """Base exception for all pipeline errors."""
    pass


class ParameterValidationError(DPSteelError):
    """Raised when a ParameterSchema definition is invalid.
    E.g. min > max, reference outside range, missing required field.
    """
    pass


class PhysicalConstraintError(DPSteelError):
    """Raised when a generated sample violates a physical constraint.
    E.g. C11 < C12, xi_inf < xi_0.
    Severity: critical (pipeline should abort) or warning (log and continue).
    """
    def __init__(self, message: str, constraint_name: str, severity: str = "critical"):
        super().__init__(message)
        self.constraint_name = constraint_name
        self.severity = severity  # "critical" | "warning"


class SamplingError(DPSteelError):
    """Raised when LHS sampling fails or produces invalid values (NaN, inf)."""
    pass


class NeperError(DPSteelError):
    """Raised when a Neper command fails or produces no output file."""
    def __init__(self, message: str, command: str = "", return_code: int = -1):
        super().__init__(message)
        self.command = command
        self.return_code = return_code


class DAMASKError(DPSteelError):
    """Raised when DAMASK file writing or solver execution fails."""
    def __init__(self, message: str, sample_id: int = -1, return_code: int = -1):
        super().__init__(message)
        self.sample_id = sample_id
        self.return_code = return_code


class ConfigurationError(DPSteelError):
    """Raised when pipeline_config.yaml is missing required keys or has invalid values."""
    pass


class CheckpointError(DPSteelError):
    """Raised when the state file is corrupted or unreadable."""
    pass
