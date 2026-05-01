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


def test_snapshots_page_lists_dates(client, dirs):
    d = dirs["snap_dir"] / "2026-05-01"
    d.mkdir()
    (d / "Full_Garden_2026-05-01_10-00-00_day.jpg").write_bytes(b"x")
    resp = client.get("/snapshots")
    assert resp.status_code == 200
    assert b"2026-05-01" in resp.content


def test_snapshots_page_shows_thumbnails_for_date(client, dirs):
    d = dirs["snap_dir"] / "2026-05-01"
    d.mkdir()
    (d / "Full_Garden_2026-05-01_10-00-00_day.jpg").write_bytes(b"x")
    (d / "Full_Garden_2026-05-01_20-00-00_night.jpg").write_bytes(b"x")
    resp = client.get("/snapshots?date=2026-05-01")
    assert resp.status_code == 200
    assert b"Full_Garden_2026-05-01_10-00-00_day.jpg" in resp.content
    assert b"Full_Garden_2026-05-01_20-00-00_night.jpg" in resp.content


def test_snapshots_page_empty_state(client):
    resp = client.get("/snapshots")
    assert resp.status_code == 200
    assert b"No snapshots" in resp.content or b"no snapshots" in resp.content.lower()


def test_videos_page_lists_daily_videos(client, dirs):
    (dirs["video_dir"] / "timelapse_2026-05-01.mp4").write_bytes(b"x")
    (dirs["video_dir"] / "timelapse_2026-04-30.mp4").write_bytes(b"x")
    resp = client.get("/videos")
    assert resp.status_code == 200
    assert b"timelapse_2026-05-01.mp4" in resp.content
    assert b"timelapse_2026-04-30.mp4" in resp.content


def test_videos_page_lists_permanent(client, dirs):
    perm_dir = dirs["video_dir"] / "permanent"
    perm_dir.mkdir()
    (perm_dir / "timelapse_permanent_2026-05-01_12-00-00.mp4").write_bytes(b"x")
    resp = client.get("/videos")
    assert resp.status_code == 200
    assert b"timelapse_permanent_2026-05-01_12-00-00.mp4" in resp.content


def test_videos_page_empty_state(client):
    resp = client.get("/videos")
    assert resp.status_code == 200
    assert b"No videos" in resp.content or b"no videos" in resp.content.lower()


def test_settings_get_shows_current_values(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert b"192.168.1.100" in resp.content
    assert b"admin" in resp.content


def test_settings_post_writes_env(client, dirs):
    resp = client.post("/settings", data={"CAMERA_IP": "10.0.0.50", "TIMELAPSE_FPS": "30"})
    assert resp.status_code == 303
    from src.web.env_editor import read_env
    values = read_env(dirs["env_file"])
    assert values["CAMERA_IP"] == "10.0.0.50"
    assert values["TIMELAPSE_FPS"] == "30"


def test_settings_post_rejects_invalid_integer(client):
    resp = client.post(
        "/settings",
        data={"TIMELAPSE_FPS": "not_a_number"},
        follow_redirects=False,
    )
    # Re-renders the form with an error
    assert resp.status_code == 200
    assert b"not_a_number" in resp.content or b"invalid" in resp.content.lower()


def test_action_capture_redirects(client, monkeypatch):
    called = {}
    def fake_capture(cfg, client_obj, dt=None):
        called["yes"] = True
        from pathlib import Path
        return Path("/fake/snap.jpg")
    monkeypatch.setattr("src.web.app.run_capture", fake_capture)
    resp = client.post("/actions/capture")
    assert called.get("yes")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/")
    assert "watch=" in resp.headers["location"]


def test_action_timelapse_redirects(client, monkeypatch):
    def fake_build(*args, **kwargs):
        pass
    monkeypatch.setattr("src.web.app.build_timelapse", fake_build)
    resp = client.post("/actions/timelapse")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/videos")


def test_action_permanent_timelapse_redirects(client, monkeypatch):
    def fake_build(*args, **kwargs):
        pass
    monkeypatch.setattr("src.web.app.build_timelapse", fake_build)
    resp = client.post("/actions/timelapse/permanent")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/videos")


def test_api_status_video_not_ready(client):
    resp = client.get("/api/status?watch=timelapse_2026-05-01.mp4&type=video")
    assert resp.status_code == 200
    assert resp.json() == {"ready": False}


def test_api_status_video_ready(client, dirs):
    (dirs["video_dir"] / "timelapse_2026-05-01.mp4").write_bytes(b"x")
    resp = client.get("/api/status?watch=timelapse_2026-05-01.mp4&type=video")
    assert resp.status_code == 200
    assert resp.json() == {"ready": True, "file": "timelapse_2026-05-01.mp4"}


def test_api_status_permanent_not_ready(client):
    resp = client.get("/api/status?watch=timelapse_permanent_2026-05-01_12-00-00.mp4&type=permanent")
    assert resp.status_code == 200
    assert resp.json() == {"ready": False}


def test_api_status_permanent_ready(client, dirs):
    perm_dir = dirs["video_dir"] / "permanent"
    perm_dir.mkdir()
    (perm_dir / "timelapse_permanent_2026-05-01_12-00-00.mp4").write_bytes(b"x")
    resp = client.get("/api/status?watch=timelapse_permanent_2026-05-01_12-00-00.mp4&type=permanent")
    assert resp.status_code == 200
    assert resp.json() == {"ready": True, "file": "timelapse_permanent_2026-05-01_12-00-00.mp4"}


def test_api_status_snapshot_not_ready(client):
    import time
    since = time.time()
    resp = client.get(f"/api/status?watch=2026-05-01&type=snapshot&since={since}")
    assert resp.status_code == 200
    assert resp.json() == {"ready": False}


def test_api_status_snapshot_ready(client, dirs):
    import time
    since = time.time() - 5
    date_dir = dirs["snap_dir"] / "2026-05-01"
    date_dir.mkdir()
    img = date_dir / "Full_Garden_2026-05-01_10-00-00_day.jpg"
    img.write_bytes(b"x")
    resp = client.get(f"/api/status?watch=2026-05-01&type=snapshot&since={since}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert "file" in data


def test_api_status_rejects_invalid_video_name(client):
    resp = client.get("/api/status?watch=../../etc/passwd&type=video")
    assert resp.status_code == 200
    assert resp.json() == {"ready": False}


def test_api_status_rejects_invalid_permanent_name(client):
    resp = client.get("/api/status?watch=../../etc/passwd&type=permanent")
    assert resp.status_code == 200
    assert resp.json() == {"ready": False}


def test_api_status_rejects_invalid_snapshot_date(client):
    resp = client.get("/api/status?watch=../sneaky&type=snapshot&since=0")
    assert resp.status_code == 200
    assert resp.json() == {"ready": False}


def test_action_capture_redirect_includes_watch(client, monkeypatch):
    from datetime import date
    import re
    monkeypatch.setattr("src.web.app.run_capture", lambda cfg, cam: None)
    resp = client.post("/actions/capture")
    assert resp.status_code == 303
    loc = resp.headers["location"]
    today = date.today().isoformat()
    assert loc.startswith("/")
    assert f"watch={today}" in loc
    assert "type=snapshot" in loc
    assert re.search(r"since=[\d.]+", loc)


def test_action_timelapse_redirect_includes_watch(client, monkeypatch):
    from datetime import date
    monkeypatch.setattr("src.web.app.build_timelapse", lambda *a, **kw: None)
    resp = client.post("/actions/timelapse")
    assert resp.status_code == 303
    loc = resp.headers["location"]
    today = date.today().isoformat()
    assert f"watch=timelapse_{today}.mp4" in loc
    assert "type=video" in loc


def test_action_permanent_redirect_includes_watch(client, monkeypatch):
    import re
    monkeypatch.setattr("src.web.app.build_timelapse", lambda *a, **kw: None)
    resp = client.post("/actions/timelapse/permanent")
    assert resp.status_code == 303
    loc = resp.headers["location"]
    assert re.search(r"watch=timelapse_permanent_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.mp4", loc)
    assert "type=permanent" in loc
