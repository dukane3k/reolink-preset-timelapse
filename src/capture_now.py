from __future__ import annotations
import logging
from dotenv import load_dotenv
from src.config import Config, ConfigError
from src.camera import CameraClient, CameraError
from src.capture import run_capture

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("capture_now")

if __name__ == "__main__":
    load_dotenv("/app/.env")
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        log.critical("Configuration error: %s", exc)
        raise SystemExit(1)

    client = CameraClient(
        ip=cfg.camera_ip,
        username=cfg.camera_username,
        password=cfg.camera_password,
        channel=cfg.camera_channel,
        ptz_speed=cfg.ptz_speed,
    )
    try:
        path = run_capture(cfg, client)
        print(path)
    except CameraError as exc:
        log.error("Camera error: %s", exc)
        raise SystemExit(1)
