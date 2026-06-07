"""
pipeline/dataset_builder.py
Load or generate the LHS parameter dataset for a given sample size.

Responsibilities
----------------
1. Check whether a pickled dataset already exists at data/dataset_<N>.data.
   If it does, load and return it without regenerating.
2. If not, call LHSSampler to generate, validate constraints, and save.
3. Optionally export a human-readable CSV alongside the binary.

This module is the single entry point for dataset creation — main.py and
runner.py both call build_dataset() and never call LHSSampler directly.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd

from utils.logger import get_logger

log = get_logger(__name__)


def build_dataset(
    n_samples: int,
    data_dir: str | Path,
    all_params: list,        # ALL_PARAMETERS
    seed: int = 42,
    force_regen: bool = False,
    export_csv: bool = True,
) -> pd.DataFrame:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    pkl_path = data_dir / f"dataset_{n_samples}.data"
    csv_path = data_dir / f"dataset_{n_samples}.csv"

    if pkl_path.exists() and not force_regen:
        log.info("Loading existing dataset: %s", pkl_path)
        with pkl_path.open("rb") as f:
            return pickle.load(f)

    log.info("Generating LHS dataset  N=%d  seed=%d", n_samples, seed)

    from sampling.lhs_sampler import LHSSampler

    sampled = [p for p in all_params if p.role in {"independent", "loading"}]
    fixed   = [p for p in all_params if p.role == "fixed"]

    sampler = LHSSampler(sampled, seed=seed)
    dataset = sampler.sample(n=n_samples)

    # Add fixed parameters as constant columns
    for p in fixed:
        value = p.reference
        dataset[p.name] = value

    # Optional: enforce canonical column order from materials/__init__.py
    canonical_order = [p.name for p in all_params]
    dataset = dataset.reindex(columns=canonical_order)

    with pkl_path.open("wb") as f:
        pickle.dump(dataset, f, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("Saved dataset: %s  shape=%s", pkl_path.name, dataset.shape)

    if export_csv:
        dataset.to_csv(csv_path, index=False)
        log.info("Exported CSV: %s", csv_path.name)

    return dataset
