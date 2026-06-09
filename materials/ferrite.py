"""
materials/ferrite.py
Ferrite phase parameter definitions for DP800 steel.

Reference: calibrated DAMASK material.yaml + Xu & Dan (2018), Metals 8, 782.
  lattice     : cI  (BCC cubic symmetry)
  N_sl        : [12, 12]  →  {110}<111> + {112}<111>
  plastic law : phenopowerlaw

Unit convention
  Schema : MPa  (stresses),  s⁻¹  (rates),  µm  (lengths),  –  (dimensionless)
  YAML   : Pa   (stresses)   →  material_writer applies unit_factor = 1e6

Texture / orientation:
  Grain orientations are assigned by Neper during tessellation using the
  ODF measured from EBSD. Euler angles are therefore NOT independent parameters —
  they are generated stochastically by Neper per RVE realisation.

Fixed parameters (not entering LHS):
  dot_gamma_0_sl = 0.001 s⁻¹  (degenerate with axial_strain_rate)
  h_sl-sl        = [1, 1.4, 1, 1.4, ...]  24-element interaction matrix
                   (not identifiable from uniaxial macro data)
"""

from core.parameter_schema import ParameterSchema

FERRITE_PARAMETERS: list[ParameterSchema] = [

    # ── Elastic constants ─────────────────────────────────────────────────────
    ParameterSchema(
        name="ferr_C11",
        physical_name="Elastic stiffness C11 (Ferrite)",
        latex_symbol=r"C_{11}^{\mathrm{ferr}}",
        damask_key="C_11",
        phase="Ferrite",
        reference=233300.0,
        min_val=210000.0,
        max_val=260000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="elastic",
    ),
    ParameterSchema(
        name="ferr_C12",
        physical_name="Elastic stiffness C12 (Ferrite)",
        latex_symbol=r"C_{12}^{\mathrm{ferr}}",
        damask_key="C_12",
        phase="Ferrite",
        reference=135500.0,
        min_val=118000.0,
        max_val=155000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="elastic",
    ),
    ParameterSchema(
        name="ferr_C44",
        physical_name="Elastic stiffness C44 (Ferrite)",
        latex_symbol=r"C_{44}^{\mathrm{ferr}}",
        damask_key="C_44",
        phase="Ferrite",
        reference=128000.0,
        min_val=112000.0,
        max_val=145000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="elastic",
    ),

    # ── Kinetic law ───────────────────────────────────────────────────────────
    ParameterSchema(
        name="ferr_dot_gamma_0_sl",
        physical_name="Reference shear rate γ̇₀ (Ferrite)",
        latex_symbol=r"\dot{\gamma}_0^{\mathrm{ferr}}",
        damask_key="dot_gamma_0_sl",
        phase="Ferrite",
        reference=0.001, min_val=0.001, max_val=0.001,
        unit="1/s", distribution="uniform", role="fixed", param_type="rate",
    ),
    ParameterSchema(
        name="ferr_n_sl",
        physical_name="Power law exponent n=1/m (Ferrite)",
        latex_symbol=r"n_{\mathrm{sl}}^{\mathrm{ferr}}",
        damask_key="n_sl",
        phase="Ferrite",
        reference=20.0,
        min_val=12.0,
        max_val=25.0,
        unit="-", distribution="uniform", role="independent", param_type="constant",
    ),

    # ── Initial CRSS — per slip family ────────────────────────────────────────
    ParameterSchema(
        name="ferr_xi_0_sl_1",
        physical_name="Initial CRSS {110}<111> (Ferrite)",
        latex_symbol=r"\xi_0^{\{110\},\mathrm{ferr}}",
        damask_key="xi_0_sl[0]",
        phase="Ferrite",
        reference=95.0, min_val=75.0, max_val=120.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),
    ParameterSchema(
        name="ferr_xi_0_sl_2",
        physical_name="Initial CRSS {112}<111> (Ferrite)",
        latex_symbol=r"\xi_0^{\{112\},\mathrm{ferr}}",
        damask_key="xi_0_sl[1]",
        phase="Ferrite",
        reference=96.0, min_val=76.0, max_val=121.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),

    # ── Saturation CRSS — per slip family ─────────────────────────────────────
    ParameterSchema(
        name="ferr_xi_inf_sl_1",
        physical_name="Saturation CRSS {110}<111> (Ferrite)",
        latex_symbol=r"\xi_\infty^{\{110\},\mathrm{ferr}}",
        damask_key="xi_inf_sl[0]",
        phase="Ferrite",
        reference=222.0, min_val=160.0, max_val=300.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),
    ParameterSchema(
        name="ferr_xi_inf_sl_2",
        physical_name="Saturation CRSS {112}<111> (Ferrite)",
        latex_symbol=r"\xi_\infty^{\{112\},\mathrm{ferr}}",
        damask_key="xi_inf_sl[1]",
        phase="Ferrite",
        reference=412.0, min_val=300.0, max_val=550.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),

    # ── Hardening modulus and exponent ────────────────────────────────────────
    ParameterSchema(
        name="ferr_h0_sl",
        physical_name="Initial hardening rate h₀ (Ferrite)",
        latex_symbol=r"h_0^{\mathrm{ferr}}",
        damask_key="h_0_sl-sl",
        phase="Ferrite",
        reference=1000.0, min_val=500.0, max_val=2000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),
    ParameterSchema(
        name="ferr_a_sl",
        physical_name="Hardening exponent a_sl (Ferrite)",
        latex_symbol=r"a_{\mathrm{sl}}^{\mathrm{ferr}}",
        damask_key="a_sl",
        phase="Ferrite",
        reference=2.25, min_val=1.5, max_val=3.5,
        unit="-", distribution="uniform", role="independent", param_type="constant",
    ),

    # ── Grain size ─────────────────────────────────────────────────────────────
    ParameterSchema(
        name="ferr_grain_s_mean",
        physical_name="Mean grain size (Ferrite)",
        latex_symbol=r"\bar{d}^{\mathrm{ferr}}",
        damask_key=None,
        phase="Ferrite",
        reference=5.0, min_val=1.0, max_val=16.0,
        unit="µm", distribution="log", role="independent", param_type="length",
        notes="Sampled ferrite equivalent grain-size mean passed to Neper.",
    ),
    ParameterSchema(
        name="ferr_grain_s_ratio",
        physical_name="Grain size std/mean ratio (Ferrite)",
        latex_symbol=r"r_d^{\mathrm{ferr}}",
        damask_key=None,
        phase="Ferrite",
        reference=0.20, min_val=0.10, max_val=0.35,
        unit="-", distribution="uniform", role="independent", param_type="ratio",
        notes="Dimensionless spread ratio r = std / mean for ferrite grain-size distribution.",
    ),
    ParameterSchema(
        name="ferr_grain_s_std",
        physical_name="Std grain size (Ferrite)",
        latex_symbol=r"\sigma_d^{\mathrm{ferr}}",
        damask_key=None,
        phase="Ferrite",
        reference=1.00, min_val=0.20, max_val=5.25,
        unit="µm", distribution="uniform", role="derived", param_type="length",
        notes="Derived as ferr_grain_s_mean * ferr_grain_s_ratio before Neper tessellation.",
    ),

    # ── Volume fraction ────────────────────────────────────────────────────────
    ParameterSchema(
        name="ferr_vol_fract",
        physical_name="Ferrite volume fraction",
        latex_symbol=r"f^{\mathrm{ferr}}",
        damask_key="v",
        phase="Ferrite",
        reference=0.82, min_val=0.50, max_val=0.92,
        unit="-", distribution="uniform", role="independent", param_type="ratio",
    ),
]
