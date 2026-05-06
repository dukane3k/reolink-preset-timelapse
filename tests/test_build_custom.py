import pytest
from pathlib import Path
from src.build_custom import collect_custom_snapshots


def _make_snap(root: Path, date: str, time_hms: str, label: str) -> Path:
    d = root / date
    d.mkdir(parents=True, exist_ok=True)
    name = f"cam_{date}_{time_hms}_{label}.jpg"
    p = d / name
    p.write_bytes(b"\xff\xd8")
    return p


def test_collect_custom_date_range_inclusive(tmp_path):
    _make_snap(tmp_path, "2026-04-28", "10-00-00", "day")
    _make_snap(tmp_path, "2026-04-29", "10-00-00", "day")
    _make_snap(tmp_path, "2026-04-30", "10-00-00", "day")
    _make_snap(tmp_path, "2026-05-01", "10-00-00", "day")

    result = collect_custom_snapshots(
        tmp_path,
        start_date="2026-04-29", end_date="2026-04-30",
        start_time="00:00", end_time="23:59",
        include_night=True, include_transitions=True, nth_frame=1,
    )
    dates = [p.parent.name for p in result]
    assert "2026-04-28" not in dates
    assert "2026-04-29" in dates
    assert "2026-04-30" in dates
    assert "2026-05-01" not in dates


def test_collect_custom_time_window(tmp_path):
    _make_snap(tmp_path, "2026-04-29", "06-00-00", "day")   # before window
    _make_snap(tmp_path, "2026-04-29", "10-00-00", "day")   # inside
    _make_snap(tmp_path, "2026-04-29", "14-00-00", "day")   # inside
    _make_snap(tmp_path, "2026-04-29", "20-00-00", "day")   # after window

    result = collect_custom_snapshots(
        tmp_path,
        start_date="2026-04-29", end_date="2026-04-29",
        start_time="08:00", end_time="18:00",
        include_night=True, include_transitions=True, nth_frame=1,
    )
    times = [p.stem.split("_")[2] for p in result]
    assert "10-00-00" in times
    assert "14-00-00" in times
    assert "06-00-00" not in times
    assert "20-00-00" not in times


def test_collect_custom_excludes_night(tmp_path):
    _make_snap(tmp_path, "2026-04-29", "10-00-00", "day")
    _make_snap(tmp_path, "2026-04-29", "22-00-00", "night")

    result = collect_custom_snapshots(
        tmp_path,
        start_date="2026-04-29", end_date="2026-04-29",
        start_time="00:00", end_time="23:59",
        include_night=False, include_transitions=True, nth_frame=1,
    )
    assert all("night" not in p.name for p in result)
    assert len(result) == 1


def test_collect_custom_nth_frame(tmp_path):
    for h in range(6):
        _make_snap(tmp_path, "2026-04-29", f"{10+h:02d}-00-00", "day")

    result = collect_custom_snapshots(
        tmp_path,
        start_date="2026-04-29", end_date="2026-04-29",
        start_time="00:00", end_time="23:59",
        include_night=True, include_transitions=True, nth_frame=2,
    )
    assert len(result) == 3  # 6 frames, every 2nd = 3


def test_collect_custom_empty_when_no_match(tmp_path):
    _make_snap(tmp_path, "2026-04-29", "10-00-00", "day")

    result = collect_custom_snapshots(
        tmp_path,
        start_date="2026-05-01", end_date="2026-05-02",
        start_time="00:00", end_time="23:59",
        include_night=True, include_transitions=True, nth_frame=1,
    )
    assert result == []
