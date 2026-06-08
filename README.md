# dp_steel_rve

Python package for generating and simulating dual-phase steel representative volume elements (RVEs) using Neper and DAMASK.

## Status
Current baseline:
- Neper stage completed successfully
- DAMASK stage completed successfully
- Repository is under active research development

## Purpose
`dp_steel_rve` is being developed as a modular research package for:
- microstructure-aware RVE generation
- parameter sampling for dual-phase steels
- Neper tessellation workflows
- DAMASK CPFEM simulation setup

## Project structure
```text
dp_steel_rve/
├── materials/
├── neper/
├── damask/
├── pipeline/
├── utils/
├── configs/
├── tests/
└── main.py
```

## Example usage
Dry-run for Neper stage:
```bash
python main.py --stage neper --n-samples 10 --dry-run
```

Real Neper run:
```bash
python main.py --stage neper --n-samples 10
```

DAMASK stage:
```bash
python main.py --stage damask --n-samples 10
```

Full pipeline:
```bash
python main.py
```

## Versioning
This repository follows semantic versioning:
- `v0.1.0` first stable GitHub baseline
- `v0.1.x` bug fixes
- `v0.2.x` new features
- `v1.0.0` stable research-ready release

## Tested environment
- Linux / WSL
- Python 3.11.15
- Neper 4.10.1
- DAMASK 3.0.2
- See requirements.txt for pinned Python packages

## License
Add your chosen license here.

## Notes
This repository is part of ongoing PhD research on AI for material science, dual-phase steel microstructures, and FE²-oriented simulation workflows.