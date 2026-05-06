from __future__ import annotations
import logging
import signal
import threading
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv
from src.config import Config, ConfigError
from src.camera import CameraClient, CameraError
from src.capture import run_capture
from src.lighting import get_lighting_label
from src.timelapse import collect_snapshots, collect_snapshots_through_date, build_timelapse
from src.retention import prune_timelapses

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("scheduler")

_shutdown_event = threading.Event()


def _handle_sigterm(signum, frame):
    log.info("SIGTERM received, shutting down after current cycle")
    _shutdown_event.set()


def _collect_for_date(cfg: Config, date_str: str) -> list:
    snap_root = Path(cfg.snapshot_dir)
    if cfg.timelapse_daily_mode == "cumulative":
        return collect_snapshots_through_date(snap_root, date_str, include_night=cfg.timelapse_include_night, include_transitions=cfg.timelapse_include_transitions)
    day_dir = snap_root / date_str
    return collect_snapshots(day_dir, include_night=cfg.timelapse_include_night, include_transitions=cfg.timelapse_include_transitions)


def _rebuild_timelapse(cfg: Config, date_str: str) -> None:
    snapshots = _collect_for_date(cfg, date_str)
    output = Path(cfg.timelapse_dir) / f"timelapse_{date_str}.mp4"
    try:
        build_timelapse(snapshots, output, fps=cfg.timelapse_fps, align=cfg.timelapse_align, stabilize=cfg.timelapse_stabilize, stabilize_crop=cfg.timelapse_stabilize_crop, stabilize_smoothing=cfg.timelapse_stabilize_smoothing, stabilize_shakiness=cfg.timelapse_stabilize_shakiness, subtitles=cfg.timelapse_subtitles, subtitle_every=cfg.timelapse_subtitle_every, burnin=cfg.timelapse_burnin)
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
        channel=cfg.camera_channel,
        ptz_speed=cfg.ptz_speed,
    )
    local_tz = ZoneInfo(cfg.timezone)
    interval = timedelta(minutes=cfg.snapshot_interval)
    current_date = datetime.now(tz=local_tz).date()

    log.info("Scheduler started. Interval: %d min", cfg.snapshot_interval)

    while not _shutdown_event.is_set():
        now = datetime.now(tz=local_tz)

        # Daily finalization at 00:01
        if now.date() != current_date and (now.hour, now.minute) >= (0, 1):
            log.info("New day — finalizing timelapse for %s", current_date)
            _rebuild_timelapse(cfg, str(current_date))
            prune_timelapses(
                Path(cfg.timelapse_dir),
                today=now.date(),
                retention_days=cfg.timelapse_retention_days,
                archive_every=cfg.timelapse_archive_every,
                retain_all=cfg.timelapse_retain_all,
            )
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
        sleep_secs = (next_tick - datetime.now(tz=local_tz)).total_seconds()
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
