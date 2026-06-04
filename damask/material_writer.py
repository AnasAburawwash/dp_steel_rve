"""
damask/material_writer.py
Create Ferrite.yaml, Martensite.yaml, and material.yaml for one sample.

Workflow
--------
1. Build phase dictionaries from the sampled row.
2. Save per-phase YAML files.
3. Parse Neper .tess to get grain-wise phase ids and Rodrigues orientations.
4. Convert Rodrigues vectors to DAMASK Rotation objects.
5. Add one material entry per grain in grain-id order.

DAMASK material configurations contain 'phase', 'homogenization', and 'material'
sections, and ConfigMaterial.material_add() appends a material entry [web:133][web:118].
"""

from pathlib import Path
import yaml

from damask.phase_config import PhaseConfig
from damask.tess_reader import parse_tess


HOMOGENIZATION_BLOCK = {
    'Taylor': {
        'N_constituents': 1,
        'mechanical': {'type': 'isostrain', 'output': ['F', 'P']},
    }
}


def write_phase_yamls(sample_row, sample_dir: str | Path) -> dict:
    sample_dir = Path(sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)

    ferrite = PhaseConfig('Ferrite', 'ferr', sample_row).to_yaml_dict()
    martensite = PhaseConfig('Martensite', 'mart', sample_row).to_yaml_dict()

    ferr_path = sample_dir / 'Ferrite.yaml'
    mart_path = sample_dir / 'Martensite.yaml'
    with ferr_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(ferrite, f, sort_keys=False)
    with mart_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(martensite, f, sort_keys=False)

    return {'Ferrite': ferr_path, 'Martensite': mart_path}


def write_material_yaml(sample_row, sample_dir: str | Path, damask_module) -> Path:
    sample_dir = Path(sample_dir)
    phase_paths = write_phase_yamls(sample_row, sample_dir)

    tess_file = sample_dir / 'neper' / f'{sample_dir.name}.tess'
    if not tess_file.exists():
        candidates = sorted((sample_dir / 'neper').glob('*.tess'))
        if not candidates:
            raise FileNotFoundError(f'No .tess file found in {sample_dir / "neper"}')
        tess_file = candidates[0]

    tess = parse_tess(tess_file)
    rotations = damask_module.Rotation.from_Rodrigues_vector(
        tess.rodrigues_damask,
        normalize=True,
        P=-1,
    )

    cfg = damask_module.ConfigMaterial()
    cfg['homogenization'] = HOMOGENIZATION_BLOCK
    cfg['phase']['Ferrite'] = damask_module.ConfigMaterial.load(str(phase_paths['Ferrite']))
    cfg['phase']['Martensite'] = damask_module.ConfigMaterial.load(str(phase_paths['Martensite']))

    for idx, phase_id in enumerate(tess.phase_idxs):
        phase_name = 'Ferrite' if phase_id == 1 else 'Martensite'
        cfg = cfg.material_add(
            homogenization='Taylor',
            phase=phase_name,
            O=rotations[idx],
        )

    out_path = sample_dir / 'material.yaml'
    cfg.save(str(out_path))
    return out_path
