from __future__ import annotations
import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


def _require(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise ConfigError(f"Missing required env var: {key}")
    return val


def _bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("1", "true", "yes")


def _int(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        raise ConfigError(f"Invalid integer for {key}: {val!r}")


def _float_required(key: str) -> float:
    val = _require(key)
    try:
        return float(val)
    except ValueError:
        raise ConfigError(f"Invalid float for {key}: {val!r}")


@dataclass
class Config:
    camera_ip: str
    camera_username: str
    camera_password: str
    preset_name: str
    home_preset: str
    ptz_settle_delay: int
    snapshot_interval: int
    snapshot_24_7: bool
    latitude: float
    longitude: float
    timezone: str
    sunrise_sunset_window: int
    timelapse_include_night: bool
    timelapse_include_transitions: bool
    timelapse_fps: int
    snapshot_dir: str
    timelapse_dir: str
    camera_channel: int
    ptz_speed: int
    timelapse_retention_days: int
    timelapse_archive_every: int
    timelapse_retain_all: bool
    timelapse_align: bool
    timelapse_stabilize: bool
    timelapse_stabilize_crop: int
    timelapse_stabilize_smoothing: int
    timelapse_stabilize_shakiness: int
    timelapse_subtitles: bool
    timelapse_subtitle_every: int
    timelapse_burnin: bool
    timelapse_daily_mode: str  # "day_only" | "cumulative"

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            camera_ip=_require("CAMERA_IP"),
            camera_username=_require("CAMERA_USERNAME"),
            camera_password=_require("CAMERA_PASSWORD"),
            preset_name=_require("CAMERA_PRESET_NAME"),
            home_preset=os.environ.get("CAMERA_HOME_PRESET", "").strip(),
            ptz_settle_delay=_int("PTZ_SETTLE_DELAY", 4),
            snapshot_interval=_int("SNAPSHOT_INTERVAL", 15),
            snapshot_24_7=_bool("SNAPSHOT_24_7", True),
            latitude=_float_required("LATITUDE"),
            longitude=_float_required("LONGITUDE"),
            timezone=os.environ.get("TIMEZONE", os.environ.get("TZ", "UTC")),
            sunrise_sunset_window=_int("SUNRISE_SUNSET_WINDOW", 30),
            timelapse_include_night=_bool("TIMELAPSE_INCLUDE_NIGHT", True),
            timelapse_include_transitions=_bool("TIMELAPSE_INCLUDE_TRANSITIONS", True),
            timelapse_fps=_int("TIMELAPSE_FPS", 24),
            snapshot_dir=_require("SNAPSHOT_DIR"),
            timelapse_dir=_require("TIMELAPSE_DIR"),
            camera_channel=_int("CAMERA_CHANNEL", 0),
            ptz_speed=_int("PTZ_SPEED", 32),
            timelapse_retention_days=_int("TIMELAPSE_RETENTION_DAYS", 7),
            timelapse_archive_every=_int("TIMELAPSE_ARCHIVE_EVERY", 7),
            timelapse_retain_all=_bool("TIMELAPSE_RETAIN_ALL", False),
            timelapse_align=_bool("TIMELAPSE_ALIGN", True),
            timelapse_stabilize=_bool("TIMELAPSE_STABILIZE", False),
            timelapse_stabilize_crop=_int("TIMELAPSE_STABILIZE_CROP", 5),
            timelapse_stabilize_smoothing=_int("TIMELAPSE_STABILIZE_SMOOTHING", 5),
            timelapse_stabilize_shakiness=_int("TIMELAPSE_STABILIZE_SHAKINESS", 5),
            timelapse_subtitles=_bool("TIMELAPSE_SUBTITLES", True),
            timelapse_subtitle_every=_int("TIMELAPSE_SUBTITLE_EVERY", 1),
            timelapse_burnin=_bool("TIMELAPSE_BURNIN", False),
            timelapse_daily_mode=os.environ.get("TIMELAPSE_DAILY_MODE", "day_only").strip() or "day_only",
        )
