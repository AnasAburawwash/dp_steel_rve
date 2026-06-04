"""
utils/paths.py
Path utilities with execution-environment awareness.

Supports three environments:
    WSL     — Windows paths converted to /mnt/<drive>/...
    LINUX   — native Linux paths, no conversion (HPC clusters)
    WINDOWS — native Windows paths (future use)

The active environment is determined by:
    1. Explicit argument to to_executor_path()
    2. ENV variable DP_STEEL_ENV  (set in shell or sbatch script)
    3. Auto-detection via platform.system() + /proc/version WSL check

Usage
-----
    from utils.paths import to_executor_path, ensure_dir, ExecutionEnvironment

    path = to_executor_path(Path("E:/PhD/cp_projects/N_500"), ExecutionEnvironment.WSL)
    # → "/mnt/e/PhD/cp_projects/N_500"

    # On HPC: set DP_STEEL_ENV=linux in your .bashrc or sbatch script
    # No code changes needed — to_executor_path() returns path unchanged.
"""

import os
import platform
from enum import Enum
from pathlib import Path, PureWindowsPath


class ExecutionEnvironment(Enum):
    WSL     = "wsl"      # Windows Subsystem for Linux (current)
    LINUX   = "linux"    # Native Linux — HPC clusters, no path conversion
    WINDOWS = "windows"  # Native Windows (future)


def detect_environment() -> ExecutionEnvironment:
    """
    Auto-detect the execution environment.

    Priority:
    1. DP_STEEL_ENV environment variable ("wsl" | "linux" | "windows")
    2. /proc/version contains "microsoft" → WSL
    3. platform.system() == "Windows" → WINDOWS
    4. Fallback → LINUX
    """
    env_var = os.environ.get("DP_STEEL_ENV", "").lower()
    if env_var in {e.value for e in ExecutionEnvironment}:
        return ExecutionEnvironment(env_var)

    # WSL detection via /proc/version
    proc_version = Path("/proc/version")
    if proc_version.exists():
        try:
            content = proc_version.read_text(encoding="utf-8", errors="ignore").lower()
            if "microsoft" in content or "wsl" in content:
                return ExecutionEnvironment.WSL
        except OSError:
            pass

    if platform.system() == "Windows":
        return ExecutionEnvironment.WINDOWS

    return ExecutionEnvironment.LINUX


def to_executor_path(path: str | Path, env: ExecutionEnvironment | None = None) -> str:
    """
    Convert a path to the string form expected by the current executor.

    Parameters
    ----------
    path : str | Path
    env  : ExecutionEnvironment | None
        If None, calls detect_environment().

    Returns
    -------
    str — ready to pass to subprocess or neper/DAMASK CLI

    Examples
    --------
    WSL:
        "E:\\PhD\\cp_projects"  →  "/mnt/e/PhD/cp_projects"
        Path("/mnt/e/PhD/...")     →  "/mnt/e/PhD/..."   (already correct)

    LINUX:
        "/scratch/user/cp_projects"  →  "/scratch/user/cp_projects"  (unchanged)

    WINDOWS:
        Path("/mnt/e/PhD/...")  →  "E:\\PhD\\..."  (future)
    """
    if env is None:
        env = detect_environment()

    path_str = str(path)

    if env == ExecutionEnvironment.WSL:
        return _to_wsl_path(path_str)
    elif env == ExecutionEnvironment.LINUX:
        # Native Linux — return as-is (forward slashes, absolute)
        return path_str.replace("\\", "/")
    elif env == ExecutionEnvironment.WINDOWS:
        # Convert /mnt/e/... back to E:/... for native Windows (future)
        return _to_windows_path(path_str)
    return path_str


# Keep the old name as an alias so existing call sites don't break
def to_wsl_path(path: str | Path) -> str:
    """Alias for to_executor_path(..., ExecutionEnvironment.WSL)."""
    return to_executor_path(path, ExecutionEnvironment.WSL)


def _to_wsl_path(path_str: str) -> str:
    """Convert a Windows-style path to a WSL /mnt/<drive>/... path."""
    p = path_str.replace("\\", "/")
    # Already a WSL/Linux path
    if p.startswith("/"):
        return p
    # Windows drive letter: E:/... → /mnt/e/...
    if len(p) >= 2 and p[1] == ":":
        drive  = p[0].lower()
        rest   = p[2:].lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return p


def _to_windows_path(path_str: str) -> str:
    """Convert a WSL /mnt/<drive>/... path back to Windows E:\\... form."""
    p = path_str.replace("\\", "/")
    if p.startswith("/mnt/") and len(p) > 6:
        drive = p[5].upper()
        rest  = p[6:].lstrip("/").replace("/", "\\")
        return f"{drive}:/{rest}"
    return p


# ── Filesystem helpers ────────────────────────────────────────────────────────

def ensure_dir(path: str | Path) -> Path:
    """Create directory (and parents) if it does not exist. Returns Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_vtk_file(folder_path: str | Path) -> Path | None:
    """Return the first .vtk or .vti file found in folder_path, or None."""
    folder = Path(folder_path)
    for ext in ("*.vtk", "*.vti"):
        candidates = sorted(folder.glob(ext))
        if candidates:
            return candidates[0]
    return None


def file_exists(file_path: str | Path) -> bool:
    return Path(file_path).exists()


def is_size_less_than(file_path: str | Path, max_size_bytes: int) -> bool:
    """Return True if the file is smaller than max_size_bytes."""
    return Path(file_path).stat().st_size < max_size_bytes


def hpc_path(path: str | Path) -> str:
    """
    Stub for HPC path resolution.
    On HPC clusters, override this to map local paths to scratch/work paths.
    Currently returns the Linux-converted path unchanged.
    """
    return to_executor_path(path, ExecutionEnvironment.LINUX)
