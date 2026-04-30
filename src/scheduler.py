from __future__ import annotations
import logging
import signal
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from src.config import Config, ConfigError
from src.camera import CameraClient, CameraError
from src.capture import run_capture
from src.lighting import get_lighting_label
from src.timelapse import collect_snapshots, build_timelapse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("scheduler")

_shutdown_event = threading.Event()


def _handle_sigterm(signum, frame):
    log.info("SIGTERM received, shutting down after current cycle")
    _shutdown_event.set()


def _rebuild_timelapse(cfg: Config, date_str: str) -> None:
    snapshot_dir = Path(cfg.snapshot_dir) / date_str
    snapshots = collect_snapshots(snapshot_dir, include_night=cfg.timelapse_include_night)
    output = Path(cfg.timelapse_dir) / f"timelapse_{date_str}.mp4"
    try:
        build_timelapse(snapshots, output, fps=cfg.timelapse_fps)
    except Exception as exc:
        log.error("Timelapse build failed: %s", exc)


def run(cfg: Config) -> None:
    _shutdown_event.clear()
    Path(cfg.snapshot_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.timelapse_dir).mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)
    client = CameraClient(
        ip=cfg.camera_ip,
        username=cfg.camera_username,
        password=cfg.camera_password,
    )
    interval = timedelta(minutes=cfg.snapshot_interval)
    current_date = datetime.now(tz=timezone.utc).date()

    log.info("Scheduler started. Interval: %d min", cfg.snapshot_interval)

    while not _shutdown_event.is_set():
        now = datetime.now(tz=timezone.utc)

        # Midnight rotation
        if now.date() != current_date:
            log.info("New day — finalizing timelapse for %s", current_date)
            _rebuild_timelapse(cfg, str(current_date))
            current_date = now.date()

        # Skip night captures if not 24/7
        if not cfg.snapshot_24_7:
            label = get_lighting_label(now, cfg.latitude, cfg.longitude, cfg.sunrise_sunset_window, cfg.timezone)
            if label == "night":
                log.info("Night — skipping capture (SNAPSHOT_24_7=false)")
                _shutdown_event.wait(timeout=60)
                continue

        try:
            run_capture(cfg, client, now)
            _rebuild_timelapse(cfg, str(now.date()))
        except CameraError as exc:
            log.error("Camera error: %s", exc)
        except Exception as exc:
            log.error("Unexpected error during capture: %s", exc)

        if _shutdown_event.is_set():
            break

        next_tick = now + interval
        sleep_secs = (next_tick - datetime.now(tz=timezone.utc)).total_seconds()
        if sleep_secs > 0:
            log.info("Next capture in %.0f seconds", sleep_secs)
            _shutdown_event.wait(timeout=sleep_secs)

    log.info("Scheduler stopped")


if __name__ == "__main__":
    load_dotenv("/app/.env")
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        log.critical("Configuration error: %s", exc)
        raise SystemExit(1)
    run(cfg)
