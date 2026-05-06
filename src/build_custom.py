from __future__ import annotations
import re
from datetime import time
from pathlib import Path

from src.timelapse import collect_snapshots, _parse_snapshot_dt


def collect_custom_snapshots(
    snapshot_root: Path,
    start_date: str,
    end_date: str,
    start_time: str,
    end_time: str,
    include_night: bool,
    include_transitions: bool,
    nth_frame: int,
) -> list[Path]:
    if nth_frame < 1:
        raise ValueError(f"nth_frame must be >= 1, got {nth_frame}")
    t_start = _parse_time(start_time)
    t_end = _parse_time(end_time)

    all_files: list[Path] = []
    if not snapshot_root.exists():
        return []

    for day_dir in sorted(d for d in snapshot_root.iterdir() if d.is_dir() and start_date <= d.name <= end_date):
        day_files = collect_snapshots(day_dir, include_night=include_night, include_transitions=include_transitions)
        for f in day_files:
            ft = _frame_time(f)
            if ft is not None and t_start <= ft <= t_end:
                all_files.append(f)

    return all_files[::nth_frame]


def count_custom_snapshots(
    snapshot_root: Path,
    start_date: str,
    end_date: str,
    start_time: str,
    end_time: str,
    include_night: bool,
    include_transitions: bool,
    nth_frame: int,
) -> int:
    return len(collect_custom_snapshots(
        snapshot_root, start_date, end_date, start_time, end_time,
        include_night, include_transitions, nth_frame,
    ))


def _parse_time(t: str) -> time:
    """Parse a time string in HH:MM format.

    Raises ValueError if the string is malformed or contains invalid time values.
    """
    h, m = t.split(":")
    return time(int(h), int(m))


def _frame_time(path: Path) -> time | None:
    """Extract time from snapshot, stripping seconds for time range comparison.

    Returns time(hour, minute) only (seconds are dropped) so comparisons match user intent
    (e.g., frame at 23:59:30 matches end_time="23:59").
    """
    dt = _parse_snapshot_dt(path)
    if not dt:
        return None
    return time(dt.hour, dt.minute)


def slugify(name: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:max_len]
