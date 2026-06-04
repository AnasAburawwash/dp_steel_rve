"""
materials/loading.py
Loading condition parameter definitions.

Currently supports uniaxial tension only.
Designed for future extension to multiaxial loading without breaking changes:
  - Add new ParameterSchema entries to LOADING_PARAMETERS
  - Add corresponding load_writer logic in damask/load_writer.py
  - Pipeline reads role='loading' automatically — no other changes needed
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.parameter_schema import ParameterSchema

LOADING_PARAMETERS: dict[str, ParameterSchema] = {

    "axial_strain_rate": ParameterSchema(
        name="axial_strain_rate",
        physical_name="Axial strain rate (uniaxial tension)",
        latex_symbol=r"$\dot{\varepsilon}$",
        damask_key="dot_F",          # Maps to deformation gradient rate in DAMASK load.yaml
        phase="Global",
        reference=1e-3,
        min_val=1e-4,
        max_val=1e-1,
        unit="s-1",
        damask_unit="s-1",
        unit_factor=1.0,
        role="loading",
        distribution="log",          # 3-decade span → log-uniform required
        param_type="rate",
        constraint_group="",
        notes=(
            "Uniaxial tension along X-axis. "
            "Log-uniform sampling over 3 decades. "
            "Future: extend with biaxial_ratio, shear_rate for multiaxial loading."
        )
    ),

    # ── Future extension placeholders (role='fixed' until implemented) ───
    # "biaxial_ratio": ParameterSchema(
    #     name="biaxial_ratio",
    #     physical_name="Biaxial stress ratio (sigma_y / sigma_x)",
    #     ...
    #     role="fixed",
    #     notes="Set to 0.0 for uniaxial; activate for multiaxial study"
    # ),
}
