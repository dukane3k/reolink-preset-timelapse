from __future__ import annotations
import re
from datetime import time
from pathlib import Path

from src.timelapse import collect_snapshots

_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})")


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
    h, m = t.split(":")
    return time(int(h), int(m))


def _frame_time(path: Path) -> time | None:
    m = _TIMESTAMP_RE.search(path.stem)
    if not m:
        return None
    return time(int(m.group(2)), int(m.group(3)), int(m.group(4)))


def slugify(name: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:max_len]
