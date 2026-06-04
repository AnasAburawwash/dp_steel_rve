"""
damask/load_writer.py
Create the DAMASK load-case YAML for uniaxial tension using sampled axial strain rate.

The load case is kept deliberately simple: one mechanical solver block and one loading path.
The sampled parameter axial_strain_rate is written into the boundary condition so the AI model
can learn rate sensitivity.
"""

from pathlib import Path
import yaml


def build_uniaxial_tension_load(axial_strain_rate: float, total_time: float = 100.0, n_increments: int = 100) -> dict:
    axial_strain_rate = float(axial_strain_rate)
    return {
        'solver': {'mechanical': 'spectral_basic'},
        'loadstep': [
            {
                'boundary_conditions': {
                    'mechanical': {
                        'dot_F': [[axial_strain_rate, 0.0, 0.0],
                                  [0.0, 'x', 0.0],
                                  [0.0, 0.0, 'x']],
                        'P': [['x', 0.0, 0.0],
                              [0.0, 0.0, 0.0],
                              [0.0, 0.0, 0.0]],
                    }
                },
                'discretization': {'t': float(total_time), 'N': int(n_increments)},
                'f_out': 1,
            }
        ],
    }


def write_load_yaml(sample_row, sample_dir: str | Path, filename: str = 'tensionX.yaml') -> Path:
    sample_dir = Path(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)
    load_dict = build_uniaxial_tension_load(sample_row['axial_strain_rate'])
    out_path = sample_dir / filename
    with out_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(load_dict, f, sort_keys=False)
    return out_path
