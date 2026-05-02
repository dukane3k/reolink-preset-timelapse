import os
import pytest
from src.config import Config, ConfigError


def test_config_loads_required_fields(tmp_path, monkeypatch):
    env = {
        "CAMERA_IP": "192.168.1.50",
        "CAMERA_USERNAME": "admin",
        "CAMERA_PASSWORD": "pass123",
        "CAMERA_PRESET_NAME": "full garden",
        "PTZ_SETTLE_DELAY": "4",
        "SNAPSHOT_INTERVAL": "15",
        "SNAPSHOT_24_7": "true",
        "LATITUDE": "41.8781",
        "LONGITUDE": "-87.6298",
        "SUNRISE_SUNSET_WINDOW": "30",
        "TIMELAPSE_INCLUDE_NIGHT": "true",
        "TIMELAPSE_FPS": "24",
        "SNAPSHOT_DIR": "/data/snapshots",
        "TIMELAPSE_DIR": "/data/timelapse",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    cfg = Config.from_env()

    assert cfg.camera_ip == "192.168.1.50"
    assert cfg.camera_username == "admin"
    assert cfg.camera_password == "pass123"
    assert cfg.preset_name == "full garden"
    assert cfg.ptz_settle_delay == 4
    assert cfg.snapshot_interval == 15
    assert cfg.snapshot_24_7 is True
    assert cfg.latitude == 41.8781
    assert cfg.longitude == -87.6298
    assert cfg.sunrise_sunset_window == 30
    assert cfg.timelapse_include_night is True
    assert cfg.timelapse_fps == 24
    assert cfg.snapshot_dir == "/data/snapshots"
    assert cfg.timelapse_dir == "/data/timelapse"


def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("CAMERA_IP", raising=False)
    with pytest.raises(ConfigError, match="CAMERA_IP"):
        Config.from_env()


def test_config_snapshot_24_7_false(monkeypatch):
    env = {
        "CAMERA_IP": "192.168.1.50",
        "CAMERA_USERNAME": "admin",
        "CAMERA_PASSWORD": "pass",
        "CAMERA_PRESET_NAME": "garden",
        "PTZ_SETTLE_DELAY": "3",
        "SNAPSHOT_INTERVAL": "10",
        "SNAPSHOT_24_7": "false",
        "LATITUDE": "41.0",
        "LONGITUDE": "-87.0",
        "SUNRISE_SUNSET_WINDOW": "20",
        "TIMELAPSE_INCLUDE_NIGHT": "false",
        "TIMELAPSE_FPS": "30",
        "SNAPSHOT_DIR": "/snapshots",
        "TIMELAPSE_DIR": "/timelapse",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    cfg = Config.from_env()
    assert cfg.snapshot_24_7 is False
    assert cfg.timelapse_include_night is False


def test_config_timelapse_daily_mode_defaults_to_day_only(monkeypatch):
    monkeypatch.delenv("TIMELAPSE_DAILY_MODE", raising=False)
    for k, v in {
        "CAMERA_IP": "x", "CAMERA_USERNAME": "a", "CAMERA_PASSWORD": "b",
        "CAMERA_PRESET_NAME": "g", "LATITUDE": "0", "LONGITUDE": "0",
        "SNAPSHOT_DIR": "/s", "TIMELAPSE_DIR": "/t",
    }.items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg.timelapse_daily_mode == "day_only"


def test_config_timelapse_daily_mode_cumulative(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_DAILY_MODE", "cumulative")
    for k, v in {
        "CAMERA_IP": "x", "CAMERA_USERNAME": "a", "CAMERA_PASSWORD": "b",
        "CAMERA_PRESET_NAME": "g", "LATITUDE": "0", "LONGITUDE": "0",
        "SNAPSHOT_DIR": "/s", "TIMELAPSE_DIR": "/t",
    }.items():
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg.timelapse_daily_mode == "cumulative"
