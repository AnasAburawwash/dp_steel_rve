"""
pipeline/state_manager.py
Atomic per-sample status tracking with JSON checkpoint files.

Each N_<n> dataset folder gets one checkpoint file:
    E:/PhD/cp_projects/N_500/pipeline_state.json

Structure
---------
{
  "meta": {"n_samples": 500, "created": "2026-06-02T10:00:00", "version": 1},
  "samples": {
    "0":   {"neper": "DONE",    "damask": "DONE",    "updated": "..."},
    "1":   {"neper": "DONE",    "damask": "FAILED",  "updated": "..."},
    "2":   {"neper": "PENDING", "damask": "PENDING", "updated": "..."},
    ...
  }
}

Status values per stage
-----------------------
PENDING  : not yet started
RUNNING  : currently executing (set at start, reset to FAILED on restart if stuck)
DONE     : completed successfully
FAILED   : subprocess returned non-zero exit or raised an exception
SKIPPED  : intentionally skipped (e.g. dry_run=True)

Thread safety
-------------
File writes use atomic rename (write tmp → os.replace) so a crash mid-write
never corrupts the checkpoint.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

Stage   = Literal["neper", "damask"]
Status  = Literal["PENDING", "RUNNING", "DONE", "FAILED", "SKIPPED"]
STAGES: tuple[Stage, ...] = ("neper", "damask")

_DEFAULT = {s: "PENDING" for s in STAGES}

CHECKPOINT_FILENAME = "pipeline_state.json"
_VERSION = 1


class StateManager:
    """
    Manages the pipeline checkpoint file for one dataset size (N_<n>).

    Parameters
    ----------
    dataset_dir : Path
        The N_<n> folder (e.g. E:/PhD/cp_projects/N_500).
    n_samples : int
        Total number of samples in this dataset.
    """

    def __init__(self, dataset_dir: str | Path, n_samples: int):
        self.dataset_dir = Path(dataset_dir)
        self.n_samples   = int(n_samples)
        self._path       = self.dataset_dir / CHECKPOINT_FILENAME
        self._lock       = Lock()
        self._state      = self._load_or_init()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_status(self, sample_id: int, stage: Stage) -> Status:
        with self._lock:
            return self._state["samples"][str(sample_id)][stage]

    def set_status(self, sample_id: int, stage: Stage, status: Status) -> None:
        with self._lock:
            entry = self._state["samples"][str(sample_id)]
            entry[stage]     = status
            entry["updated"] = _now()
            self._save()

    def is_done(self, sample_id: int, stage: Stage) -> bool:
        return self.get_status(sample_id, stage) == "DONE"

    def pending_ids(self, stage: Stage) -> list[int]:
        """Return sample IDs with status PENDING for a given stage."""
        with self._lock:
            return [
                int(sid)
                for sid, entry in self._state["samples"].items()
                if entry[stage] == "PENDING"
            ]

    def failed_ids(self, stage: Stage) -> list[int]:
        with self._lock:
            return [
                int(sid)
                for sid, entry in self._state["samples"].items()
                if entry[stage] == "FAILED"
            ]

    def reset_failed(self, stage: Stage) -> int:
        """Reset FAILED → PENDING for the given stage. Returns count reset."""
        with self._lock:
            count = 0
            for entry in self._state["samples"].values():
                if entry[stage] == "FAILED":
                    entry[stage] = "PENDING"
                    count += 1
            if count:
                self._save()
            return count

    def reset_running(self, stage: Stage) -> int:
        """
        Reset RUNNING → FAILED on startup (crash recovery).
        Any sample marked RUNNING at init time was interrupted mid-execution.
        """
        with self._lock:
            count = 0
            for entry in self._state["samples"].values():
                if entry[stage] == "RUNNING":
                    entry[stage] = "FAILED"
                    count += 1
            if count:
                self._save()
            return count

    def summary(self) -> dict:
        """Return counts per stage per status."""
        with self._lock:
            out = {}
            for stage in STAGES:
                counts: dict[str, int] = {}
                for entry in self._state["samples"].values():
                    s = entry[stage]
                    counts[s] = counts.get(s, 0) + 1
                out[stage] = counts
            return out

    def print_summary(self) -> None:
        s = self.summary()
        print(f"  State: {self._path.name}  (N={self.n_samples})")
        for stage in STAGES:
            counts = s[stage]
            parts  = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"    {stage:>8}: {parts}")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_or_init(self) -> dict:
        """Load existing checkpoint or create a fresh one."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                # Crash-recovery: reset any RUNNING entries
                for stage in STAGES:
                    count = 0
                    for entry in data["samples"].values():
                        if entry.get(stage) == "RUNNING":
                            entry[stage] = "FAILED"
                            count += 1
                if count:
                    self._state = data
                    self._save()
                return data
            except (json.JSONDecodeError, KeyError):
                pass  # corrupted — reinitialise

        data = {
            "meta": {
                "n_samples": self.n_samples,
                "created":   _now(),
                "version":   _VERSION,
            },
            "samples": {
                str(i): {**_DEFAULT, "updated": _now()}
                for i in range(self.n_samples)
            },
        }
        self._state = data
        self._save()
        return data

    def _save(self) -> None:
        """Atomic write: tmp file → os.replace to avoid partial writes."""
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
