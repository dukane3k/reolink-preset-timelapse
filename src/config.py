from __future__ import annotations
import os
from dataclasses import dataclass


class ConfigError(Exception):
    pass


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ConfigError(f"Missing required env var: {key}")
    return val


def _bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("1", "true", "yes")


@dataclass
class Config:
    camera_ip: str
    camera_username: str
    camera_password: str
    preset_name: str
    ptz_settle_delay: int
    snapshot_interval: int
    snapshot_24_7: bool
    latitude: float
    longitude: float
    sunrise_sunset_window: int
    timelapse_include_night: bool
    timelapse_fps: int
    snapshot_dir: str
    timelapse_dir: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            camera_ip=_require("CAMERA_IP"),
            camera_username=_require("CAMERA_USERNAME"),
            camera_password=_require("CAMERA_PASSWORD"),
            preset_name=_require("CAMERA_PRESET_NAME"),
            ptz_settle_delay=int(os.environ.get("PTZ_SETTLE_DELAY", "4")),
            snapshot_interval=int(os.environ.get("SNAPSHOT_INTERVAL", "15")),
            snapshot_24_7=_bool("SNAPSHOT_24_7", True),
            latitude=float(_require("LATITUDE")),
            longitude=float(_require("LONGITUDE")),
            sunrise_sunset_window=int(os.environ.get("SUNRISE_SUNSET_WINDOW", "30")),
            timelapse_include_night=_bool("TIMELAPSE_INCLUDE_NIGHT", True),
            timelapse_fps=int(os.environ.get("TIMELAPSE_FPS", "24")),
            snapshot_dir=_require("SNAPSHOT_DIR"),
            timelapse_dir=_require("TIMELAPSE_DIR"),
        )
