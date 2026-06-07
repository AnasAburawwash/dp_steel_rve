"""Materials module for dp_steel_rve."""

from .ferrite import FERRITE_PARAMETERS
from .martensite import MARTENSITE_PARAMETERS
from .loading import LOADING_PARAMETERS

ALL_PARAMETERS = FERRITE_PARAMETERS + MARTENSITE_PARAMETERS + [LOADING_PARAMETERS["axial_strain_rate"]]

__all__ = [
    "ALL_PARAMETERS",
    "FERRITE_PARAMETERS",
    "MARTENSITE_PARAMETERS",
    "LOADING_PARAMETERS",
]