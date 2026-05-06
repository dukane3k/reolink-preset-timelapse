from __future__ import annotations
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from src.config import Config, ConfigError
from src.timelapse import collect_snapshots, build_timelapse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("build_permanent")


def build_permanent(cfg: Config, now: datetime | None = None) -> Path:
    if now is None:
        now = datetime.now(tz=timezone.utc)

    snapshot_root = Path(cfg.snapshot_dir)
    all_snapshots = []
    for date_dir in sorted(snapshot_root.iterdir()):
        if not date_dir.is_dir():
            continue
        all_snapshots.extend(collect_snapshots(date_dir, include_night=cfg.timelapse_include_night, include_transitions=cfg.timelapse_include_transitions))

    timestamp = now.astimezone(ZoneInfo(cfg.timezone)).strftime("%Y-%m-%d_%H-%M-%S")
    permanent_dir = Path(cfg.timelapse_dir) / "permanent"
    output = permanent_dir / f"timelapse_permanent_{timestamp}.mp4"

    build_timelapse(all_snapshots, output, fps=cfg.timelapse_fps, align=cfg.timelapse_align, stabilize=cfg.timelapse_stabilize, stabilize_crop=cfg.timelapse_stabilize_crop, stabilize_smoothing=cfg.timelapse_stabilize_smoothing, stabilize_shakiness=cfg.timelapse_stabilize_shakiness, subtitles=cfg.timelapse_subtitles, subtitle_every=cfg.timelapse_subtitle_every, burnin=cfg.timelapse_burnin)
    return output


if __name__ == "__main__":
    load_dotenv("/app/.env")
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        logging.critical("Configuration error: %s", exc)
        raise SystemExit(1)

    try:
        path = build_permanent(cfg)
        print(path)
    except Exception as exc:
        log.error("Failed to build permanent timelapse: %s", exc)
        raise SystemExit(1)
