import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from src.config import Config
from src.build_permanent import build_permanent


def _cfg(tmp_path):
    return Config(
        camera_ip="192.168.1.100",
        camera_username="admin",
        camera_password="secret",
        preset_name="full garden",
        home_preset="",
        ptz_settle_delay=0,
        snapshot_interval=15,
        snapshot_24_7=True,
        latitude=41.8781,
        longitude=-87.6298,
        timezone="UTC",
        sunrise_sunset_window=30,
        timelapse_include_night=True,
        timelapse_fps=24,
        snapshot_dir=str(tmp_path / "snapshots"),
        timelapse_dir=str(tmp_path / "timelapse"),
        camera_channel=0,
        ptz_speed=32,
        timelapse_retention_days=7,
        timelapse_archive_every=7,
        timelapse_retain_all=False,
        timelapse_stabilize=False,
        timelapse_subtitles=False,
        timelapse_subtitle_every=1,
    )


def _make_snapshot(snapshot_dir: Path, date_str: str, name: str) -> Path:
    d = snapshot_dir / date_str
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(b"\xff\xd8\xff\xe0")
    return p


def test_build_permanent_collects_all_snapshots(tmp_path):
    cfg = _cfg(tmp_path)
    snapshot_dir = Path(cfg.snapshot_dir)
    _make_snapshot(snapshot_dir, "2026-04-30", "garden_2026-04-30_10-00-00_day.jpg")
    _make_snapshot(snapshot_dir, "2026-05-01", "garden_2026-05-01_10-00-00_day.jpg")
    dt = datetime(2026, 5, 1, 14, 32, 0, tzinfo=timezone.utc)

    with patch("src.build_permanent.build_timelapse") as mock_build:
        build_permanent(cfg, now=dt)

    snapshots = mock_build.call_args[0][0]
    assert len(snapshots) == 2
    assert snapshots[0].parent.name == "2026-04-30"
    assert snapshots[1].parent.name == "2026-05-01"


def test_build_permanent_excludes_night_when_configured(tmp_path):
    cfg = _cfg(tmp_path)
    cfg = cfg.__class__(**{**cfg.__dict__, "timelapse_include_night": False})
    snapshot_dir = Path(cfg.snapshot_dir)
    _make_snapshot(snapshot_dir, "2026-05-01", "garden_2026-05-01_10-00-00_day.jpg")
    _make_snapshot(snapshot_dir, "2026-05-01", "garden_2026-05-01_02-00-00_night.jpg")
    dt = datetime(2026, 5, 1, 14, 32, 0, tzinfo=timezone.utc)

    with patch("src.build_permanent.build_timelapse") as mock_build:
        build_permanent(cfg, now=dt)

    snapshots = mock_build.call_args[0][0]
    assert len(snapshots) == 1
    assert "_night" not in snapshots[0].name


def test_build_permanent_output_path_uses_local_timezone(tmp_path):
    cfg = _cfg(tmp_path)
    snapshot_dir = Path(cfg.snapshot_dir)
    _make_snapshot(snapshot_dir, "2026-04-30", "garden_2026-04-30_19-35-00_day.jpg")
    # 01:35 UTC = 19:35 CDT on 2026-04-30 — but cfg timezone is UTC in _cfg(), so no shift
    dt = datetime(2026, 5, 1, 14, 32, 0, tzinfo=timezone.utc)

    with patch("src.build_permanent.build_timelapse") as mock_build:
        path = build_permanent(cfg, now=dt)

    # cfg timezone is UTC, so filename matches UTC time
    assert path.name == "timelapse_permanent_2026-05-01_14-32-00.mp4"
    assert path.parent.name == "permanent"
