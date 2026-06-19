"""
main.py
Entry point for the DP800 CP parameter study pipeline.

Usage
-----
    # Full pipeline for all dataset sizes:
    python main.py

    # Single stage for one dataset size:
    python main.py --stage neper --n-samples 500

    # Resume after interruption:
    python main.py --resume

    # Retry only failed samples:
    python main.py --retry-failed

    # Dry run (build commands, no execution):
    python main.py --dry-run

    # Regenerate LHS datasets:
    python main.py --force-regen

    # Override environment (useful on HPC):
    python main.py --env linux

    # Override config file:
    python main.py --config ./configs/pipeline_config.yaml
"""

import argparse
import os
import sys
from pathlib import Path
import importlib.metadata

import yaml

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="DP800 CP FE² parameter study pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--config",       default="./configs/pipeline_config.yaml",
                   help="Path to pipeline_config.yaml")
    p.add_argument("--stage",        choices=["all", "neper", "damask"], default="all",
                   help="Which stage(s) to run")
    p.add_argument("--n-samples",    type=int, default=None,
                   help="Run for a single dataset size only")
    p.add_argument("--resume",       action="store_true",
                   help="Skip already DONE samples (default behaviour)")
    p.add_argument("--retry-failed", action="store_true",
                   help="Reset FAILED → PENDING before running")
    p.add_argument("--dry-run",      action="store_true",
                   help="Build commands but do not execute")
    p.add_argument("--force-regen",  action="store_true",
                   help="Regenerate LHS datasets even if files exist")
    p.add_argument("--env",          choices=["wsl", "linux", "windows"], default=None,
                   help="Override execution environment (default: auto-detect)")
    p.add_argument("--log-level",    default=None,
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                   help="Override log level from config")
    p.add_argument("--batch-index", type=int, default=None,
               help="LSF job array index (1-based, from $LSB_JOBINDEX). "
                    "If set, only process samples in this batch.")
    p.add_argument("--batch-size",  type=int, default=50,
               help="Number of samples per array task (default: 50).")
    return p.parse_args()


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        print(f"[ERROR] Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    args = parse_args()
    cfg  = load_config(args.config)

    # ── Environment override ───────────────────────────────────────────────
    if args.env:
        os.environ["DP_STEEL_ENV"] = args.env
    elif "environment" in cfg:
        os.environ.setdefault("DP_STEEL_ENV", cfg["environment"])

    # ── Logging ────────────────────────────────────────────────────────────
    from utils.logger import configure_logging
    log_level = args.log_level or cfg.get("logging", {}).get("level", "INFO")
    configure_logging(
        log_dir = Path(cfg.get("log_dir", "./logs")),
        level   = log_level,
    )
    from utils.logger import get_logger
    log = get_logger("main")

    log.info("DP800 CP pipeline starting")
    log.info("Config: %s", args.config)
    log.info("Stage:  %s  |  dry_run: %s  |  retry_failed: %s",
             args.stage, args.dry_run, args.retry_failed)

    # ── Materials & parameters ─────────────────────────────────────────────
    from materials import ALL_PARAMETERS

    # ── DAMASK import (lazy — allows pipeline to start without DAMASK) ─────
    if args.stage in ("all", "damask") and not args.dry_run:
        try:
            import damask
            try:
                damask_version = importlib.metadata.version("damask")
            except importlib.metadata.PackageNotFoundError:
                damask_version = "unknown"
            log.info("DAMASK version: %s", damask_version)
        except ImportError:
            log.error("DAMASK Python package not found. Install it or use --dry-run.")
            sys.exit(1)

    # ── Dataset sizes ──────────────────────────────────────────────────────
    # Single master dataset — n_samples from config or CLI override
    n_samples_cfg = cfg.get("n_samples", 50)
    sizes = [args.n_samples if args.n_samples else n_samples_cfg]

    base_dir = Path(cfg["base_dir"])
    data_dir = Path(cfg.get("data_dir", "./data"))

    # ── Run pipeline for each N ────────────────────────────────────────────
    from pipeline.runner import run_pipeline_for_n

    for n in sizes:
        try:
            run_pipeline_for_n(
                n_samples    = n,
                base_dir     = base_dir,
                data_dir     = data_dir,
                all_params   = ALL_PARAMETERS,
                cfg          = cfg,
                stage        = args.stage,
                dry_run      = args.dry_run,
                retry_failed = args.retry_failed,
                force_regen  = args.force_regen,
                batch_index  = args.batch_index,
                batch_size   = args.batch_size,
            )
        except KeyboardInterrupt:
            log.warning("Interrupted by user. Progress saved in checkpoint files.")
            sys.exit(0)
        except Exception as exc:
            log.error("Pipeline failed for N=%d: %s", n, exc, exc_info=True)
            log.info("Continuing to next dataset size...")

    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
