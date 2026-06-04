"""
utils/logger.py
Structured logger with console + rotating file handlers.

Usage
-----
    from utils.logger import get_logger, configure_logging

    # In main.py — configure once at startup:
    configure_logging(log_dir=Path("E:/PhD/cp_projects/logs"), level="INFO")

    # In any module:
    log = get_logger(__name__)
    log.info("Sample %04d complete", sample_id)

Log files
---------
    logs/pipeline_<YYYYMMDD_HHMMSS>.log   — full run log
    logs/pipeline_latest.log              — symlink to latest (Linux only)
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False
_LOG_FORMAT  = "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    log_dir:    str | Path | None = None,
    level:      str = "INFO",
    max_bytes:  int = 10 * 1024 * 1024,   # 10 MB per file
    backup_count: int = 3,
) -> None:
    """
    Configure root logger with console + optional file handler.

    Call once at pipeline startup (main.py). Subsequent calls are no-ops
    unless reconfigure=True is passed.

    Parameters
    ----------
    log_dir      : Path | None — if given, write rotating log files here
    level        : str         — "DEBUG" | "INFO" | "WARNING" | "ERROR"
    max_bytes    : int         — max size per log file before rotation
    backup_count : int         — number of rotated files to keep
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
    root.addHandler(console)

    # File handler — full DEBUG log
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"pipeline_{ts}.log"
        fh = RotatingFileHandler(
            log_file,
            maxBytes    = max_bytes,
            backupCount = backup_count,
            encoding    = "utf-8",
        )
        fh.setFormatter(formatter)
        fh.setLevel(logging.DEBUG)
        root.addHandler(fh)

        # Latest symlink (Linux/WSL only — skip on Windows)
        try:
            latest = log_dir / "pipeline_latest.log"
            if latest.is_symlink():
                latest.unlink()
            latest.symlink_to(log_file.name)
        except (OSError, NotImplementedError):
            pass

        root.info("Logging to: %s", log_file)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.
    If configure_logging() has not been called yet, falls back to
    basicConfig so the logger is still usable in tests and sub-processes.
    """
    if not _configured:
        logging.basicConfig(
            format  = _LOG_FORMAT,
            datefmt = _DATE_FORMAT,
            level   = logging.INFO,
            stream  = sys.stdout,
        )
    return logging.getLogger(name)
