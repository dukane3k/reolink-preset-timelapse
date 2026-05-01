from pathlib import Path
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def dirs(tmp_path):
    snap_dir = tmp_path / "snapshots"
    video_dir = tmp_path / "timelapse"
    snap_dir.mkdir()
    video_dir.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAMERA_IP=192.168.1.100\n"
        "CAMERA_USERNAME=admin\n"
        "CAMERA_PASSWORD=secret\n"
        "CAMERA_PRESET_NAME=Garden\n"
        "CAMERA_HOME_PRESET=\n"
        "PTZ_SETTLE_DELAY=4\n"
        "PTZ_SPEED=32\n"
        "SNAPSHOT_INTERVAL=15\n"
        "SNAPSHOT_24_7=true\n"
        "LATITUDE=41.8827\n"
        "LONGITUDE=-87.6233\n"
        "TIMEZONE=America/Chicago\n"
        "SUNRISE_SUNSET_WINDOW=30\n"
        "TIMELAPSE_INCLUDE_NIGHT=true\n"
        "TIMELAPSE_FPS=24\n"
        "SNAPSHOT_DIR=/data/snapshots\n"
        "TIMELAPSE_DIR=/data/timelapse\n"
        "CAMERA_CHANNEL=0\n"
        "TIMELAPSE_RETENTION_DAYS=7\n"
        "TIMELAPSE_ARCHIVE_EVERY=7\n"
        "TIMELAPSE_RETAIN_ALL=false\n"
        "TIMELAPSE_ALIGN=true\n"
        "TIMELAPSE_STABILIZE=false\n"
        "TIMELAPSE_STABILIZE_CROP=5\n"
        "TIMELAPSE_STABILIZE_SMOOTHING=5\n"
        "TIMELAPSE_STABILIZE_SHAKINESS=5\n"
        "TIMELAPSE_SUBTITLES=true\n"
        "TIMELAPSE_SUBTITLE_EVERY=1\n"
        "TIMELAPSE_BURNIN=false\n"
        "TIMELAPSE_BURNIN_EVERY=30\n"
    )
    return {"snap_dir": snap_dir, "video_dir": video_dir, "env_file": env_file}


@pytest.fixture
def client(dirs):
    from src.web.app import create_app
    app = create_app(
        snapshot_dir=dirs["snap_dir"],
        timelapse_dir=dirs["video_dir"],
        env_path=dirs["env_file"],
    )
    return TestClient(app, follow_redirects=False)


def test_media_snapshot_serves_existing_file(client, dirs):
    date_dir = dirs["snap_dir"] / "2026-05-01"
    date_dir.mkdir()
    img = date_dir / "Full_Garden_2026-05-01_10-00-00_day.jpg"
    img.write_bytes(b"FAKEJPEG")
    resp = client.get("/media/snapshots/2026-05-01/Full_Garden_2026-05-01_10-00-00_day.jpg")
    assert resp.status_code == 200
    assert resp.content == b"FAKEJPEG"


def test_media_snapshot_returns_404_for_missing(client):
    resp = client.get("/media/snapshots/2026-05-01/nonexistent.jpg")
    assert resp.status_code == 404


def test_media_video_serves_existing_file(client, dirs):
    mp4 = dirs["video_dir"] / "timelapse_2026-05-01.mp4"
    mp4.write_bytes(b"FAKEMP4")
    resp = client.get("/media/videos/timelapse_2026-05-01.mp4")
    assert resp.status_code == 200
    assert resp.content == b"FAKEMP4"


def test_media_video_returns_404_for_missing(client):
    resp = client.get("/media/videos/nonexistent.mp4")
    assert resp.status_code == 404


def test_dashboard_renders_empty_state(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"No snapshots yet" in resp.content or b"no snapshots" in resp.content.lower()


def test_dashboard_shows_latest_snapshot(client, dirs):
    date_dir = dirs["snap_dir"] / "2026-05-01"
    date_dir.mkdir()
    img = date_dir / "Full_Garden_2026-05-01_10-00-00_day.jpg"
    img.write_bytes(b"FAKEJPEG")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Full_Garden_2026-05-01_10-00-00_day.jpg" in resp.content


def test_dashboard_shows_todays_video(client, dirs):
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    mp4 = dirs["video_dir"] / f"timelapse_{today}.mp4"
    mp4.write_bytes(b"FAKEMP4")
    resp = client.get("/")
    assert resp.status_code == 200
    assert today.encode() in resp.content


def test_dashboard_has_action_buttons(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"/actions/capture" in resp.content
    assert b"/actions/timelapse" in resp.content
