from __future__ import annotations
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from src.config import Config
from src.camera import CameraClient
from src.lighting import get_lighting_label

log = logging.getLogger(__name__)


def build_snapshot_path(cfg: Config, dt: datetime, label: str) -> Path:
    local_dt = dt.astimezone(ZoneInfo(cfg.timezone))
    date_str = local_dt.strftime("%Y-%m-%d")
    time_str = local_dt.strftime("%H-%M-%S")
    preset_slug = cfg.preset_name.replace(" ", "_")
    filename = f"{preset_slug}_{date_str}_{time_str}_{label}.jpg"
    directory = Path(cfg.snapshot_dir) / date_str
    return directory / filename


def run_capture(cfg: Config, client: CameraClient, dt: datetime | None = None) -> Path:
    if dt is None:
        dt = datetime.now(tz=timezone.utc)

    label = get_lighting_label(dt, cfg.latitude, cfg.longitude, cfg.sunrise_sunset_window, cfg.timezone)

    preset_id = client.get_preset_id(cfg.preset_name)
    client.goto_preset(preset_id)

    if cfg.ptz_settle_delay > 0:
        time.sleep(cfg.ptz_settle_delay)

    client._set_osd_time(False)
    try:
        image_bytes = client.fetch_snapshot()
    finally:
        client._set_osd_time(True)

    if cfg.home_preset:
        home_id = client.get_preset_id(cfg.home_preset)
        client.goto_preset(home_id)

    path = build_snapshot_path(cfg, dt, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    log.info("Saved snapshot: %s", path)
    return path
