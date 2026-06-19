"""
sampling/generate_samples.py
-----------------------------
One-time script: generate the full LHS sample table for the 1000-sample run.
Run ONCE on the login node before submitting the job array:

    conda activate micro_dpsteel
    python sampling/generate_samples.py \
        --config ./configs/pipeline_config_hpc.yaml \
        --n-samples 1000 \
        --output /scratch/toso3816/rve_simulations/data/samples_1000.csv

The output CSV has columns: sample_id (0-999) + one column per LHS parameter.
All 20 array tasks read from this file — no two tasks generate overlapping IDs.
"""

import argparse
from pathlib import Path
import sys

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate LHS sample table")
    parser.add_argument("--config",    required=True)
    parser.add_argument("--n-samples", type=int, default=1000)
    parser.add_argument("--output",    required=True)
    parser.add_argument("--seed",      type=int, default=None,
                        help="Override seed from config")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    seed = args.seed if args.seed is not None else cfg.get("seed", 42)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Import the project's own dataset builder so LHS logic is shared
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from materials import ALL_PARAMETERS
    from pipeline.dataset_builder import build_dataset

    dataset = build_dataset(
        n_samples   = args.n_samples,
        data_dir    = output.parent,
        all_params  = ALL_PARAMETERS,
        seed        = seed,
        force_regen = True,
        export_csv  = True,
    )

    dataset.to_csv(output, index_label="sample_id")
    print(f"Saved {len(dataset)} samples → {output}")
    print(f"Columns: {list(dataset.columns)}")


if __name__ == "__main__":
    main()