"""
materials/martensite.py
Martensite phase parameter definitions for DP800 steel.

Reference: calibrated DAMASK material.yaml + Xu & Dan (2018), Metals 8, 782.
  lattice     : cI  (BCC approximation for low-carbon BCT, c/a ≈ 1)
  N_sl        : [12, 12]  →  {110}<111> + {112}<111>
  plastic law : phenopowerlaw

Unit convention: same as ferrite.py (MPa in schema, Pa in YAML).

Texture / orientation:
  Same rationale as ferrite — grain orientations assigned by Neper from ODF.
  Euler angles are NOT independent parameters.

n_sl range shifted higher vs ferrite (less rate-sensitive BCT):
  ferrite   n ∈ [12, 25]  (m ∈ [0.040, 0.083])
  martensite n ∈ [15, 30]  (m ∈ [0.033, 0.067])
  Physically justified by initial ρ_mart ~ 10¹³ vs ρ_ferr ~ 10⁹ m⁻²
  (Xu & Dan 2018, Table 4).
"""

from core.parameter_schema import ParameterSchema

MARTENSITE_PARAMETERS: list[ParameterSchema] = [

    # ── Elastic constants ─────────────────────────────────────────────────────
    ParameterSchema(
        name="mart_C11",
        physical_name="Elastic stiffness C11 (Martensite)",
        latex_symbol=r"C_{11}^{\mathrm{mart}}",
        damask_key="C_11",
        phase="Martensite",
        reference=417400.0, min_val=380000.0, max_val=460000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="elastic",
    ),
    ParameterSchema(
        name="mart_C12",
        physical_name="Elastic stiffness C12 (Martensite)",
        latex_symbol=r"C_{12}^{\mathrm{mart}}",
        damask_key="C_12",
        phase="Martensite",
        reference=242400.0, min_val=215000.0, max_val=275000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="elastic",
    ),
    ParameterSchema(
        name="mart_C44",
        physical_name="Elastic stiffness C44 (Martensite)",
        latex_symbol=r"C_{44}^{\mathrm{mart}}",
        damask_key="C_44",
        phase="Martensite",
        reference=211100.0, min_val=185000.0, max_val=240000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="elastic",
    ),

    # ── Kinetic law ───────────────────────────────────────────────────────────
    ParameterSchema(
        name="mart_dot_gamma_0_sl",
        physical_name="Reference shear rate γ̇₀ (Martensite)",
        latex_symbol=r"\dot{\gamma}_0^{\mathrm{mart}}",
        damask_key="dot_gamma_0_sl",
        phase="Martensite",
        reference=0.001, min_val=0.001, max_val=0.001,
        unit="1/s", distribution="uniform", role="fixed", param_type="rate",
    ),
    ParameterSchema(
        name="mart_n_sl",
        physical_name="Power law exponent n=1/m (Martensite)",
        latex_symbol=r"n_{\mathrm{sl}}^{\mathrm{mart}}",
        damask_key="n_sl",
        phase="Martensite",
        reference=20.0, min_val=15.0, max_val=30.0,
        unit="-", distribution="uniform", role="independent", param_type="constant",
    ),

    # ── Initial CRSS — per slip family ────────────────────────────────────────
    ParameterSchema(
        name="mart_xi_0_sl_1",
        physical_name="Initial CRSS {110}<111> (Martensite)",
        latex_symbol=r"\xi_0^{\{110\},\mathrm{mart}}",
        damask_key="xi_0_sl[0]",
        phase="Martensite",
        reference=406.0, min_val=300.0, max_val=520.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),
    ParameterSchema(
        name="mart_xi_0_sl_2",
        physical_name="Initial CRSS {112}<111> (Martensite)",
        latex_symbol=r"\xi_0^{\{112\},\mathrm{mart}}",
        damask_key="xi_0_sl[1]",
        phase="Martensite",
        reference=457.0, min_val=340.0, max_val=580.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),

    # ── Saturation CRSS — per slip family ─────────────────────────────────────
    ParameterSchema(
        name="mart_xi_inf_sl_1",
        physical_name="Saturation CRSS {110}<111> (Martensite)",
        latex_symbol=r"\xi_\infty^{\{110\},\mathrm{mart}}",
        damask_key="xi_inf_sl[0]",
        phase="Martensite",
        reference=873.0, min_val=600.0, max_val=1100.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),
    ParameterSchema(
        name="mart_xi_inf_sl_2",
        physical_name="Saturation CRSS {112}<111> (Martensite)",
        latex_symbol=r"\xi_\infty^{\{112\},\mathrm{mart}}",
        damask_key="xi_inf_sl[1]",
        phase="Martensite",
        reference=971.0, min_val=650.0, max_val=1250.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),

    # ── Hardening modulus and exponent ────────────────────────────────────────
    ParameterSchema(
        name="mart_h0_sl",
        physical_name="Initial hardening rate h₀ (Martensite)",
        latex_symbol=r"h_0^{\mathrm{mart}}",
        damask_key="h_0_sl-sl",
        phase="Martensite",
        reference=563000.0, min_val=300000.0, max_val=800000.0,
        unit="MPa", distribution="uniform", role="independent", param_type="stress",
    ),
    ParameterSchema(
        name="mart_a_sl",
        physical_name="Hardening exponent a_sl (Martensite)",
        latex_symbol=r"a_{\mathrm{sl}}^{\mathrm{mart}}",
        damask_key="a_sl",
        phase="Martensite",
        reference=2.25, min_val=1.5, max_val=3.5,
        unit="-", distribution="uniform", role="independent", param_type="constant",
    ),

    # ── Grain size ─────────────────────────────────────────────────────────────
    ParameterSchema(
        name="mart_grain_s_mean",
        physical_name="Mean grain size (Martensite)",
        latex_symbol=r"\bar{d}^{\mathrm{mart}}",
        damask_key=None,
        phase="Martensite",
        reference=0.3, min_val=0.1, max_val=6.0,
        unit="µm", distribution="log", role="independent", param_type="length",
    ),
    
    ParameterSchema(
        name="mart_grain_s_ratio",
        physical_name="Grain size std/mean ratio (Martensite)",
        latex_symbol=r"r_d^{\mathrm{mart}}",
        damask_key=None,
        phase="Martensite",
        reference=0.20, min_val=0.10, max_val=0.35,
        unit="-", distribution="uniform", role="independent", param_type="ratio",
        notes="Dimensionless spread ratio r = std / mean for martensite grain-size distribution.",
    ),

    ParameterSchema(
        name="mart_grain_s_std",
        physical_name="Std grain size (Martensite)",
        latex_symbol=r"\sigma_d^{\mathrm{mart}}",
        damask_key=None,
        phase="Martensite",
        reference=0.60, min_val=0.10, max_val=2.80,
        unit="µm", distribution="uniform", role="derived", param_type="length",
        notes="Derived as mart_grain_s_mean * mart_grain_s_ratio before Neper tessellation.",
    ),

    # ── Volume fraction ────────────────────────────────────────────────────────
    ParameterSchema(
        name="mart_vol_fract",
        physical_name="Martensite volume fraction",
        latex_symbol=r"f^{\mathrm{mart}}",
        damask_key="v",
        phase="Martensite",
        reference=0.18, min_val=0.08, max_val=0.50,
        unit="-", distribution="uniform", role="derived", param_type="ratio",
    ),
]
