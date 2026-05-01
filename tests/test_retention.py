import pytest
from datetime import date
from pathlib import Path
from src.retention import prune_timelapses


def _make_timelapse(directory: Path, d: date) -> Path:
    p = directory / f"timelapse_{d}.mp4"
    p.write_bytes(b"fake")
    return p


def test_files_within_retention_are_kept(tmp_path):
    today = date(2026, 5, 10)
    _make_timelapse(tmp_path, date(2026, 5, 9))  # 1 day ago
    _make_timelapse(tmp_path, date(2026, 5, 7))  # 3 days ago

    prune_timelapses(tmp_path, today=today, retention_days=7, archive_every=7)

    assert len(list(tmp_path.glob("*.mp4"))) == 2


def test_old_non_archive_files_are_deleted(tmp_path):
    today = date(2026, 5, 10)
    # 8 days ago — outside retention, not on a 7-day boundary
    old = _make_timelapse(tmp_path, date(2026, 5, 2))

    prune_timelapses(tmp_path, today=today, retention_days=7, archive_every=7)

    assert not old.exists()


def test_old_archive_files_are_kept(tmp_path):
    today = date(2026, 5, 10)
    # 14 days ago — outside retention, exactly on a 7-day boundary
    archive = _make_timelapse(tmp_path, date(2026, 4, 26))

    prune_timelapses(tmp_path, today=today, retention_days=7, archive_every=7)

    assert archive.exists()


def test_mixed_old_files(tmp_path):
    today = date(2026, 5, 10)
    keep = _make_timelapse(tmp_path, date(2026, 4, 26))   # 14 days ago — archive boundary
    delete = _make_timelapse(tmp_path, date(2026, 4, 27)) # 13 days ago — not on boundary

    prune_timelapses(tmp_path, today=today, retention_days=7, archive_every=7)

    assert keep.exists()
    assert not delete.exists()


def test_unrelated_files_are_not_touched(tmp_path):
    today = date(2026, 5, 10)
    other = tmp_path / "permanent_timelapse.mp4"
    other.write_bytes(b"fake")

    prune_timelapses(tmp_path, today=today, retention_days=7, archive_every=7)

    assert other.exists()
