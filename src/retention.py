from __future__ import annotations
import logging
import re
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

_DATE_RE = re.compile(r"timelapse_(\d{4}-\d{2}-\d{2})\.mp4$")


def _parse_date(path: Path) -> date | None:
    m = _DATE_RE.search(path.name)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def prune_timelapses(
    timelapse_dir: Path,
    today: date,
    retention_days: int,
    archive_every: int,
    retain_all: bool = False,
) -> None:
    """Delete timelapse MP4s outside the retention window that don't fall on an archive interval."""
    if retain_all:
        return

    cutoff = today - timedelta(days=retention_days)

    candidates: list[tuple[date, Path]] = []
    for p in timelapse_dir.glob("timelapse_*.mp4"):
        d = _parse_date(p)
        if d is not None and d < cutoff:
            candidates.append((d, p))

    for d, p in candidates:
        days_ago = (today - d).days
        if days_ago % archive_every == 0:
            continue
        log.info("Pruning timelapse: %s", p.name)
        p.unlink()
