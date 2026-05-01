import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone
from pathlib import Path
from src.capture import build_snapshot_path, run_capture
from src.config import Config


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
    )


def test_build_snapshot_path_format(tmp_path):
    cfg = _cfg(tmp_path)
    dt = datetime(2026, 4, 30, 14, 32, 0, tzinfo=timezone.utc)
    path = build_snapshot_path(cfg, dt, "day")
    assert path.name == "full_garden_2026-04-30_14-32-00_day.jpg"
    assert path.parent.name == "2026-04-30"


def test_build_snapshot_path_uses_local_timezone(tmp_path):
    cfg = Config(
        camera_ip="192.168.1.100",
        camera_username="admin",
        camera_password="secret",
        preset_name="garden",
        home_preset="",
        ptz_settle_delay=0,
        snapshot_interval=15,
        snapshot_24_7=True,
        latitude=41.8781,
        longitude=-87.6298,
        timezone="America/Chicago",
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
    )
    # 01:35 UTC = 19:35 CDT (UTC-5) on the previous calendar day
    dt = datetime(2026, 5, 1, 0, 35, 0, tzinfo=timezone.utc)
    path = build_snapshot_path(cfg, dt, "night")
    assert path.parent.name == "2026-04-30"
    assert "19-35-00" in path.name


def test_build_snapshot_path_spaces_replaced(tmp_path):
    cfg = _cfg(tmp_path)
    dt = datetime(2026, 4, 30, 6, 0, 0, tzinfo=timezone.utc)
    path = build_snapshot_path(cfg, dt, "sunrise")
    assert " " not in path.name


def test_run_capture_saves_file(tmp_path):
    cfg = _cfg(tmp_path)
    mock_client = MagicMock()
    mock_client.get_preset_id.return_value = 3
    mock_client.fetch_snapshot.return_value = b"\xff\xd8\xff\xe0"
    dt = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.capture.get_lighting_label", return_value="day"):
        path = run_capture(cfg, mock_client, dt)

    assert path.exists()
    assert path.read_bytes() == b"\xff\xd8\xff\xe0"


def test_run_capture_calls_goto_preset(tmp_path):
    cfg = _cfg(tmp_path)
    mock_client = MagicMock()
    mock_client.get_preset_id.return_value = 5
    mock_client.fetch_snapshot.return_value = b"\xff\xd8"
    dt = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.capture.get_lighting_label", return_value="day"):
        run_capture(cfg, mock_client, dt)

    mock_client.goto_preset.assert_called_once_with(5)
