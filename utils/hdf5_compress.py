"""
utils/hdf5_compress.py
----------------------
In-place HDF5 compression with automatic backend selection:
  1. h5repack  — preferred (fast, C-level, ships with hdf5-tools)
  2. h5py      — pure-Python fallback (always available in the conda env)

Usage (standalone test):
    python utils/hdf5_compress.py path/to/file.hdf5
    python utils/hdf5_compress.py path/to/file.hdf5 --method gzip --level 4
    python utils/hdf5_compress.py path/to/file.hdf5 --backend h5py

Pipeline usage:
    from utils.hdf5_compress import compress_hdf5
    compress_hdf5(sample_dir / "result.hdf5")
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

_H5REPACK = "h5repack"


# ── Public API ────────────────────────────────────────────────

def compress_hdf5(
    path:          str | Path,
    method:        str   = "gzip",
    level:         int   = 4,
    min_size_mb:   float = 500.0,
    keep_original: bool  = False,
    backend:       str   = "auto",   # "auto" | "h5repack" | "h5py"
) -> dict:
    """
    Compress an HDF5 file in-place.

    Parameters
    ----------
    path          : path to the .hdf5 file
    method        : 'gzip' (default) or 'lzf'  — lzf only supported by h5py backend
    level         : gzip compression level 1–9  (ignored for lzf)
    min_size_mb   : skip if file is smaller than this threshold
    keep_original : save a .hdf5.orig backup before replacing
    backend       : 'auto' tries h5repack first, falls back to h5py

    Returns
    -------
    dict: skipped, backend_used, size_before_mb, size_after_mb, ratio, elapsed_s
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"HDF5 file not found: {path}")

    size_before_mb = path.stat().st_size / 1024 ** 2

    if size_before_mb < min_size_mb:
        log.info(
            "Skipping compression: %.1f MB < threshold %.1f MB (%s)",
            size_before_mb, min_size_mb, path.name,
        )
        return {"skipped": True, "size_before_mb": size_before_mb}

    # Select backend
    use_h5repack = (
        backend == "h5repack"
        or (backend == "auto" and shutil.which(_H5REPACK) is not None)
    )
    if backend == "h5repack" and not shutil.which(_H5REPACK):
        raise RuntimeError(
            "h5repack not found on PATH. Install hdf5-tools or use backend='h5py'."
        )

    chosen = "h5repack" if use_h5repack else "h5py"
    log.info("Backend: %s | file: %s (%.1f MB)", chosen, path.name, size_before_mb)

    tmp_path = path.with_suffix(".hdf5.tmp")
    t0 = time.perf_counter()

    try:
        if use_h5repack:
            _repack_h5repack(path, tmp_path, method, level)
        else:
            _repack_h5py(path, tmp_path, method, level)

        # Integrity check (always via h5py — lightweight open/close)
        _verify_h5py(tmp_path)

        size_after_mb = tmp_path.stat().st_size / 1024 ** 2
        elapsed = time.perf_counter() - t0
        ratio = size_before_mb / size_after_mb if size_after_mb > 0 else 1.0

        if keep_original:
            shutil.copy2(path, path.with_suffix(".hdf5.orig"))
            log.info("Original backup saved: %s", path.with_suffix(".hdf5.orig").name)

        tmp_path.replace(path)   # atomic on POSIX (same filesystem)

        log.info(
            "Compressed %s: %.1f MB → %.1f MB  ratio=%.2fx  elapsed=%.1fs  backend=%s",
            path.name, size_before_mb, size_after_mb, ratio, elapsed, chosen,
        )
        return {
            "skipped":        False,
            "backend_used":   chosen,
            "size_before_mb": size_before_mb,
            "size_after_mb":  size_after_mb,
            "ratio":          ratio,
            "elapsed_s":      elapsed,
        }

    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


# ── Backends ──────────────────────────────────────────────────

def _repack_h5repack(src: Path, dst: Path, method: str, level: int) -> None:
    """Compress via h5repack (C binary — faster for large files)."""
    filter_arg = f"GZIP={level}" if method == "gzip" else "LZF"
    cmd = [_H5REPACK, "-f", filter_arg, str(src), str(dst)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"h5repack failed (rc={result.returncode}):\n{result.stderr.strip()}"
        )


def _repack_h5py(src: Path, dst: Path, method: str, level: int) -> None:
    """Compress via h5py (pure Python — portable fallback)."""
    import h5py

    compression      = method          # "gzip" or "lzf"
    compression_opts = level if method == "gzip" else None

    with h5py.File(src, "r") as f_in, h5py.File(dst, "w") as f_out:
        # Copy root-level attributes
        f_out.attrs.update(f_in.attrs)

        def _copy_item(name: str, obj: h5py.HLObject) -> None:
            if isinstance(obj, h5py.Dataset):
                chunks = obj.chunks or True   # enable auto-chunking if not already set
                f_out.create_dataset(
                    name,
                    data=obj[()],
                    compression=compression,
                    compression_opts=compression_opts,
                    chunks=chunks,
                )
                f_out[name].attrs.update(obj.attrs)
            elif isinstance(obj, h5py.Group):
                grp = f_out.require_group(name)
                grp.attrs.update(obj.attrs)

        f_in.visititems(_copy_item)


def _verify_h5py(path: Path) -> None:
    """Lightweight integrity check: open the file and read the root group."""
    import h5py
    with h5py.File(path, "r") as f:
        _ = list(f.keys())   # force a read of the root group
    log.debug("Integrity check passed: %s", path.name)


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Compress an HDF5 file in-place (h5repack or h5py fallback)"
    )
    parser.add_argument("path",           help="Path to .hdf5 file")
    parser.add_argument("--method",       default="gzip", choices=["gzip", "lzf"])
    parser.add_argument("--level",        type=int,   default=4)
    parser.add_argument("--min-size-mb",  type=float, default=50.0)
    parser.add_argument("--keep-original", action="store_true")
    parser.add_argument(
        "--backend", default="auto", choices=["auto", "h5repack", "h5py"],
        help="Force a specific backend (default: auto-detect h5repack, fallback h5py)",
    )
    args = parser.parse_args()

    stats = compress_hdf5(
        args.path,
        method=args.method,
        level=args.level,
        min_size_mb=args.min_size_mb,
        keep_original=args.keep_original,
        backend=args.backend,
    )
    if not stats.get("skipped"):
        print(
            f"\nDone [{stats['backend_used']}]  "
            f"{stats['size_before_mb']:.1f} MB → {stats['size_after_mb']:.1f} MB  "
            f"({stats['ratio']:.2f}x)  {stats['elapsed_s']:.1f}s"
        )