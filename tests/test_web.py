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


def test_media_video_supports_range_request(client, dirs):
    mp4 = dirs["video_dir"] / "timelapse_2026-05-01.mp4"
    mp4.write_bytes(b"0123456789")
    resp = client.get("/media/videos/timelapse_2026-05-01.mp4", headers={"Range": "bytes=2-5"})
    assert resp.status_code == 206
    assert resp.content == b"2345"
    assert resp.headers["content-range"] == "bytes 2-5/10"
    assert resp.headers["accept-ranges"] == "bytes"


def test_media_video_range_open_ended(client, dirs):
    mp4 = dirs["video_dir"] / "timelapse_2026-05-01.mp4"
    mp4.write_bytes(b"0123456789")
    resp = client.get("/media/videos/timelapse_2026-05-01.mp4", headers={"Range": "bytes=7-"})
    assert resp.status_code == 206
    assert resp.content == b"789"
    assert resp.headers["content-range"] == "bytes 7-9/10"


def test_media_video_no_range_returns_200_with_accept_ranges(client, dirs):
    mp4 = dirs["video_dir"] / "timelapse_2026-05-01.mp4"
    mp4.write_bytes(b"FAKEMP4DATA")
    resp = client.get("/media/videos/timelapse_2026-05-01.mp4")
    assert resp.status_code == 200
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.content == b"FAKEMP4DATA"


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
    assert b'data-ts="2026-05-01T10:00:00"' in resp.content


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


def test_snapshots_page_shows_formatted_time(client, dirs):
    d = dirs["snap_dir"] / "2026-05-01"
    d.mkdir()
    (d / "Full_Garden_2026-05-01_10-08-27_day.jpg").write_bytes(b"x")
    resp = client.get("/snapshots?date=2026-05-01")
    assert resp.status_code == 200
    # Should show formatted time like "10:08 AM" as visible text
    assert b"10:08 AM" in resp.content


def test_snapshots_page_shows_label_badge(client, dirs):
    d = dirs["snap_dir"] / "2026-05-01"
    d.mkdir()
    (d / "Full_Garden_2026-05-01_10-00-00_day.jpg").write_bytes(b"x")
    (d / "Full_Garden_2026-05-01_20-00-00_night.jpg").write_bytes(b"x")
    (d / "Full_Garden_2026-05-01_06-00-00_sunrise.jpg").write_bytes(b"x")
    (d / "Full_Garden_2026-05-01_19-00-00_sunset.jpg").write_bytes(b"x")
    resp = client.get("/snapshots?date=2026-05-01")
    assert resp.status_code == 200
    content = resp.text
    # Each label should appear as a visible badge
    assert "day" in content
    assert "night" in content
    assert "sunrise" in content
    assert "sunset" in content
    # Labels should appear in styled badge spans, not just raw filenames
    assert content.count('>day<') >= 1
    assert content.count('>night<') >= 1
    assert content.count('>sunrise<') >= 1
    assert content.count('>sunset<') >= 1


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
    assert b"Must be an integer" in resp.content


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


def test_dashboard_snapshot_iso_in_data_ts(client, dirs):
    date_dir = dirs["snap_dir"] / "2026-05-01"
    date_dir.mkdir()
    img = date_dir / "Full_Garden_2026-05-01_14-32-05_day.jpg"
    img.write_bytes(b"FAKEJPEG")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'data-ts="2026-05-01T14:32:05"' in resp.content


def test_dashboard_video_iso_in_data_ts(client, dirs):
    from datetime import date, datetime
    today = date.today().strftime("%Y-%m-%d")
    mp4 = dirs["video_dir"] / f"timelapse_{today}.mp4"
    mp4.write_bytes(b"FAKEMP4")
    mtime = mp4.stat().st_mtime
    expected_iso = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")
    resp = client.get("/")
    assert resp.status_code == 200
    assert f'data-ts="{expected_iso}"'.encode() in resp.content


def test_api_errors_returns_empty_when_docker_unavailable(client, monkeypatch):
    import docker
    monkeypatch.setattr(docker, "from_env", lambda: (_ for _ in ()).throw(Exception("Docker not available")))
    resp = client.get("/api/errors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["errors"] == []
    assert data["container_status"] == "unknown"


def test_api_errors_returns_critical_when_container_not_running(client, monkeypatch):
    import docker

    class FakeContainer:
        status = "exited"
        def logs(self, **kwargs):
            return b""

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["container_status"] == "exited"
    assert len(data["errors"]) == 1
    assert data["errors"][0]["level"] == "CRITICAL"
    assert "exited" in data["errors"][0]["message"]


def test_api_errors_parses_error_lines_from_logs(client, monkeypatch):
    import docker

    log_output = (
        b"2026-05-01T21:54:47.123456789Z 2026-05-01 21:54:47,217 ERROR scheduler Camera error: login failed\n"
        b"2026-05-01T21:55:00.000000000Z 2026-05-01 21:55:00,000 INFO scheduler Scheduler running\n"
        b"2026-05-01T21:56:00.000000000Z 2026-05-01 21:56:00,000 CRITICAL scheduler Configuration error: missing field\n"
    )

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            return log_output

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["container_status"] == "running"
    assert len(data["errors"]) == 2
    messages = [e["message"] for e in data["errors"]]
    assert any("Camera error: login failed" in m for m in messages)
    assert any("Configuration error: missing field" in m for m in messages)
    levels = [e["level"] for e in data["errors"]]
    assert "ERROR" in levels
    assert "CRITICAL" in levels


def test_api_errors_respects_since_param(client, monkeypatch):
    import docker
    captured_kwargs = {}

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            captured_kwargs.update(kwargs)
            return b""

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors?since=1746000000.0")
    assert resp.status_code == 200
    assert captured_kwargs.get("since") == 1746000000.0


def test_api_errors_caps_at_20_results(client, monkeypatch):
    import docker

    # Generate 25 error lines
    lines = b""
    for i in range(25):
        lines += f"2026-05-01T21:54:{i:02d}.000000000Z 2026-05-01 21:54:{i:02d},000 ERROR scheduler Error {i}\n".encode()

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            return lines

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    assert len(resp.json()["errors"]) == 20


def test_api_errors_ignores_error_word_in_info_message(client, monkeypatch):
    import docker

    log_output = (
        b"2026-05-01T10:00:00.000000000Z 2026-05-01 10:00:00,000 INFO scheduler Received ERROR response from camera\n"
    )

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            return log_output

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    assert resp.json()["errors"] == []


def test_api_errors_default_since_is_one_hour_ago(client, monkeypatch):
    import docker
    import time
    captured_kwargs = {}

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            captured_kwargs.update(kwargs)
            return b""

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    before = time.time() - 3600
    resp = client.get("/api/errors")  # no since param
    after = time.time() - 3600
    assert resp.status_code == 200
    assert before <= captured_kwargs.get("since", 0) <= after + 1


def test_api_log_returns_empty_when_docker_unavailable(client, monkeypatch):
    import docker
    monkeypatch.setattr(docker, "from_env", lambda: (_ for _ in ()).throw(Exception("no docker")))
    resp = client.get("/api/log")
    assert resp.status_code == 200
    assert resp.json()["lines"] == []


def test_api_log_returns_matching_build_lines(client, monkeypatch):
    import docker

    log_output = (
        b"2026-05-02T10:48:10.000000000Z 2026-05-02 10:48:10,000 INFO src.timelapse Aligning 312 frames to reference...\n"
        b"2026-05-02T10:48:10.100000000Z 2026-05-02 10:48:10,100 INFO src.alignment Aligning 312 frames, crop=5% \xe2\x86\x92 3456x1944\n"
        b"2026-05-02T10:52:00.000000000Z 2026-05-02 10:52:00,000 INFO src.alignment Aligned 312 frames\n"
        b"2026-05-02T10:52:05.000000000Z 2026-05-02 10:52:05,000 INFO scheduler Next capture in 900 seconds\n"
        b"2026-05-02T10:52:10.000000000Z 2026-05-02 10:52:10,000 INFO src.timelapse Timelapse saved: /data/timelapse/timelapse_permanent_2026-05-02_10-52-10.mp4\n"
    )

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            return log_output

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/log")
    assert resp.status_code == 200
    lines = resp.json()["lines"]
    messages = [l["message"] for l in lines]
    # Should include aligning/aligned/saved lines but not scheduler noise
    assert any("Aligning 312 frames to reference" in m for m in messages)
    assert any("Aligned 312 frames" in m for m in messages)
    assert any("Timelapse saved" in m for m in messages)
    assert not any("Next capture" in m for m in messages)
    # alignment detail line (crop=...) should be excluded too
    assert not any("crop=" in m for m in messages)


def test_api_log_respects_since_param(client, monkeypatch):
    import docker
    captured_kwargs = {}

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            captured_kwargs.update(kwargs)
            return b""

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/log?since=1746100000.0")
    assert resp.status_code == 200
    assert captured_kwargs.get("since") == 1746100000.0


# --- Delete endpoints ---

def test_delete_daily_video_removes_file(client, dirs):
    video = dirs["video_dir"] / "timelapse_2026-05-01.mp4"
    video.write_bytes(b"x")
    resp = client.delete("/api/videos/timelapse_2026-05-01.mp4")
    assert resp.status_code == 200
    assert not video.exists()


def test_delete_daily_video_returns_404_when_missing(client, dirs):
    resp = client.delete("/api/videos/timelapse_2026-05-01.mp4")
    assert resp.status_code == 404


def test_delete_permanent_video_removes_file(client, dirs):
    perm_dir = dirs["video_dir"] / "permanent"
    perm_dir.mkdir()
    video = perm_dir / "timelapse_permanent_2026-05-01.mp4"
    video.write_bytes(b"x")
    resp = client.delete("/api/videos/permanent/timelapse_permanent_2026-05-01.mp4")
    assert resp.status_code == 200
    assert not video.exists()


def test_delete_permanent_video_returns_404_when_missing(client, dirs):
    resp = client.delete("/api/videos/permanent/timelapse_permanent_2026-05-01.mp4")
    assert resp.status_code == 404


def test_delete_video_path_traversal_is_blocked(client, dirs):
    # Starlette normalizes ../ out of the URL before routing, so the request
    # lands on an unknown path and gets 404 — traversal is impossible.
    resp = client.delete("/api/videos/../secret.txt")
    assert resp.status_code == 404


def test_delete_snapshot_removes_file(client, dirs):
    day_dir = dirs["snap_dir"] / "2026-05-01"
    day_dir.mkdir()
    snap = day_dir / "2026-05-01_10-00-00_day.jpg"
    snap.write_bytes(b"x")
    resp = client.delete("/api/snapshots/2026-05-01/2026-05-01_10-00-00_day.jpg")
    assert resp.status_code == 200
    assert not snap.exists()


def test_delete_snapshot_returns_404_when_missing(client, dirs):
    resp = client.delete("/api/snapshots/2026-05-01/2026-05-01_10-00-00_day.jpg")
    assert resp.status_code == 404


def test_delete_snapshot_rejects_invalid_date(client, dirs):
    resp = client.delete("/api/snapshots/not-a-date/snap.jpg")
    assert resp.status_code == 400


def test_delete_snapshot_day_removes_directory(client, dirs):
    day_dir = dirs["snap_dir"] / "2026-05-01"
    day_dir.mkdir()
    (day_dir / "snap1.jpg").write_bytes(b"x")
    (day_dir / "snap2.jpg").write_bytes(b"x")
    resp = client.delete("/api/snapshots/2026-05-01")
    assert resp.status_code == 200
    assert not day_dir.exists()


def test_delete_snapshot_day_returns_404_when_missing(client, dirs):
    resp = client.delete("/api/snapshots/2026-05-01")
    assert resp.status_code == 404


def test_designer_page_renders(client):
    resp = client.get("/designer")
    assert resp.status_code == 200
    assert b"designer" in resp.content.lower()


def test_api_designer_frames_no_snapshots(client):
    resp = client.get("/api/designer/frames?start_date=2026-04-28&end_date=2026-04-30"
                      "&start_time=00:00&end_time=23:59&include_night=false"
                      "&include_transitions=true&nth_frame=1&fps=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["frames"] == 0
    assert data["duration_seconds"] == 0


def test_api_designer_frames_counts_matching(client, dirs):
    d = dirs["snap_dir"] / "2026-04-29"
    d.mkdir()
    (d / "cam_2026-04-29_10-00-00_day.jpg").write_bytes(b"x")
    (d / "cam_2026-04-29_14-00-00_day.jpg").write_bytes(b"x")
    (d / "cam_2026-04-29_22-00-00_night.jpg").write_bytes(b"x")

    resp = client.get("/api/designer/frames?start_date=2026-04-29&end_date=2026-04-29"
                      "&start_time=00:00&end_time=23:59&include_night=false"
                      "&include_transitions=true&nth_frame=1&fps=24")
    data = resp.json()
    assert data["frames"] == 2
    assert round(data["duration_seconds"], 1) == round(2 / 24, 1)


def test_action_timelapse_custom_redirects(client, dirs):
    from unittest.mock import patch, MagicMock
    d = dirs["snap_dir"] / "2026-04-29"
    d.mkdir()
    (d / "cam_2026-04-29_10-00-00_day.jpg").write_bytes(b"x")

    with patch("src.web.app.build_timelapse") as mock_build:
        mock_build.return_value = None
        resp = client.post("/actions/timelapse/custom", data={
            "start_date": "2026-04-29",
            "end_date": "2026-04-29",
            "start_time": "00:00",
            "end_time": "23:59",
            "include_night": "false",
            "include_transitions": "true",
            "nth_frame": "1",
            "fps_mode": "fps",
            "fps": "24",
            "target_duration": "",
            "speed_multiplier": "1",
            "align": "true",
            "stabilize": "false",
            "stabilize_crop": "5",
            "stabilize_smoothing": "5",
            "stabilize_shakiness": "5",
            "subtitles": "true",
            "subtitle_every": "1",
            "burnin": "false",
            "burnin_every": "30",
            "name": "Spring Growth",
        })
    assert resp.status_code == 303
    assert "/videos" in resp.headers["location"]


def test_action_timelapse_custom_validates_dates(client):
    resp = client.post("/actions/timelapse/custom", data={
        "start_date": "2026-04-30",
        "end_date": "2026-04-28",
        "start_time": "00:00",
        "end_time": "23:59",
        "name": "Bad",
        "fps_mode": "fps", "fps": "24",
        "nth_frame": "1",
    })
    assert resp.status_code == 303
    assert "flash" in str(resp.headers).lower() or "error" in resp.headers.get("set-cookie", "").lower()


def test_action_timelapse_custom_requires_name(client, dirs):
    d = dirs["snap_dir"] / "2026-04-29"
    d.mkdir()
    (d / "cam_2026-04-29_10-00-00_day.jpg").write_bytes(b"x")
    resp = client.post("/actions/timelapse/custom", data={
        "start_date": "2026-04-29",
        "end_date": "2026-04-29",
        "start_time": "00:00",
        "end_time": "23:59",
        "name": "",
        "fps_mode": "fps", "fps": "24",
        "nth_frame": "1",
    })
    assert resp.status_code == 303
    assert "error" in resp.headers.get("set-cookie", "").lower()


def test_delete_custom_video(client, dirs):
    custom_dir = dirs["video_dir"] / "custom"
    custom_dir.mkdir()
    f = custom_dir / "timelapse_custom_spring-growth_2026-04-29_10-00-00.mp4"
    f.write_bytes(b"FAKEMP4")
    resp = client.delete(f"/api/videos/custom/{f.name}")
    assert resp.status_code == 200
    assert not f.exists()


def test_api_status_custom_type(client, dirs):
    import time as _time
    custom_dir = dirs["video_dir"] / "custom"
    custom_dir.mkdir()
    fname = "timelapse_custom_spring_2026-04-29_10-00-00.mp4"
    since = _time.time() - 10
    f = custom_dir / fname
    f.write_bytes(b"FAKEMP4")
    resp = client.get(f"/api/status?watch={fname}&type=custom&since={since}")
    assert resp.status_code == 200
    assert resp.json()["ready"] is True
