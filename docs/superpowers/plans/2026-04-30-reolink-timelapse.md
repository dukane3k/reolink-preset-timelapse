# Reolink PTZ Timelapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized Python app that periodically moves a Reolink PTZ camera to a named preset, captures a timestamped snapshot labeled with lighting condition, and assembles a daily timelapse video.

**Architecture:** A Python scheduler loop runs `capture.py` on a configurable interval; after each capture it rebuilds the day's timelapse via `timelapse.py`; at midnight it finalizes and rotates. All config comes from a `.env` file mounted into the container.

**Tech Stack:** Python 3.12, `requests`, `astral`, `python-dotenv`, `ffmpeg`, Docker / docker-compose

---

## File Map

| File | Responsibility |
|---|---|
| `src/config.py` | Load and validate all `.env` settings into a typed `Config` dataclass |
| `src/lighting.py` | Calculate lighting label (`day`/`night`/`sunrise`/`sunset`) for a given datetime |
| `src/camera.py` | Reolink HTTP API: get presets, move PTZ, fetch snapshot bytes |
| `src/capture.py` | Orchestrate one capture: move PTZ, wait, label, save file |
| `src/timelapse.py` | Build MP4 from a directory of JPEGs using ffmpeg subprocess |
| `src/scheduler.py` | Entry point: run loop, midnight rotation, SIGTERM handling |
| `tests/test_lighting.py` | Unit tests for lighting label logic |
| `tests/test_config.py` | Unit tests for config loading/validation |
| `tests/test_capture.py` | Unit tests for filename generation and capture orchestration (camera mocked) |
| `tests/test_timelapse.py` | Unit tests for snapshot file list filtering (ffmpeg mocked) |
| `requirements.txt` | Python dependencies |
| `requirements-dev.txt` | Test dependencies (`pytest`) |
| `Dockerfile` | Container image |
| `docker-compose.yml` | Service definition with volume mounts |
| `.env.example` | Template config file |

---

## Task 1: Project Scaffold

**Files:**
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src tests docs/superpowers/plans docs/superpowers/specs
touch src/__init__.py tests/__init__.py
```

- [ ] **Step 2: Create `requirements.txt`**

```
requests==2.32.3
astral==3.2
python-dotenv==1.0.1
```

- [ ] **Step 3: Create `requirements-dev.txt`**

```
pytest==8.3.4
pytest-mock==3.14.0
```

- [ ] **Step 4: Create `.env.example`**

```env
# Camera
CAMERA_IP=192.168.1.100
CAMERA_USERNAME=admin
CAMERA_PASSWORD=secret
CAMERA_PRESET_NAME=full garden
PTZ_SETTLE_DELAY=4

# Scheduling
SNAPSHOT_INTERVAL=15
SNAPSHOT_24_7=true

# Location (for sunrise/sunset calculation)
LATITUDE=41.8781
LONGITUDE=-87.6298
SUNRISE_SUNSET_WINDOW=30

# Timelapse
TIMELAPSE_INCLUDE_NIGHT=true
TIMELAPSE_FPS=24

# Output
SNAPSHOT_DIR=/data/snapshots
TIMELAPSE_DIR=/data/timelapse
```

- [ ] **Step 5: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
*.mp4
snapshots/
```

- [ ] **Step 6: Commit**

```bash
git init
git add src/__init__.py tests/__init__.py requirements.txt requirements-dev.txt .env.example .gitignore
git commit -m "chore: project scaffold"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import os
import pytest
from src.config import Config, ConfigError


def test_config_loads_required_fields(tmp_path, monkeypatch):
    env = {
        "CAMERA_IP": "192.168.1.50",
        "CAMERA_USERNAME": "admin",
        "CAMERA_PASSWORD": "pass123",
        "CAMERA_PRESET_NAME": "full garden",
        "PTZ_SETTLE_DELAY": "4",
        "SNAPSHOT_INTERVAL": "15",
        "SNAPSHOT_24_7": "true",
        "LATITUDE": "41.8781",
        "LONGITUDE": "-87.6298",
        "SUNRISE_SUNSET_WINDOW": "30",
        "TIMELAPSE_INCLUDE_NIGHT": "true",
        "TIMELAPSE_FPS": "24",
        "SNAPSHOT_DIR": "/data/snapshots",
        "TIMELAPSE_DIR": "/data/timelapse",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    cfg = Config.from_env()

    assert cfg.camera_ip == "192.168.1.50"
    assert cfg.camera_username == "admin"
    assert cfg.camera_password == "pass123"
    assert cfg.preset_name == "full garden"
    assert cfg.ptz_settle_delay == 4
    assert cfg.snapshot_interval == 15
    assert cfg.snapshot_24_7 is True
    assert cfg.latitude == 41.8781
    assert cfg.longitude == -87.6298
    assert cfg.sunrise_sunset_window == 30
    assert cfg.timelapse_include_night is True
    assert cfg.timelapse_fps == 24
    assert cfg.snapshot_dir == "/data/snapshots"
    assert cfg.timelapse_dir == "/data/timelapse"


def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("CAMERA_IP", raising=False)
    with pytest.raises(ConfigError, match="CAMERA_IP"):
        Config.from_env()


def test_config_snapshot_24_7_false(monkeypatch):
    env = {
        "CAMERA_IP": "192.168.1.50",
        "CAMERA_USERNAME": "admin",
        "CAMERA_PASSWORD": "pass",
        "CAMERA_PRESET_NAME": "garden",
        "PTZ_SETTLE_DELAY": "3",
        "SNAPSHOT_INTERVAL": "10",
        "SNAPSHOT_24_7": "false",
        "LATITUDE": "41.0",
        "LONGITUDE": "-87.0",
        "SUNRISE_SUNSET_WINDOW": "20",
        "TIMELAPSE_INCLUDE_NIGHT": "false",
        "TIMELAPSE_FPS": "30",
        "SNAPSHOT_DIR": "/snapshots",
        "TIMELAPSE_DIR": "/timelapse",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    cfg = Config.from_env()
    assert cfg.snapshot_24_7 is False
    assert cfg.timelapse_include_night is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` for `src.config`

- [ ] **Step 3: Implement `src/config.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: config module with env loading and validation"
```

---

## Task 3: Lighting Label Module

**Files:**
- Create: `src/lighting.py`
- Create: `tests/test_lighting.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_lighting.py
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import patch, MagicMock
from src.lighting import get_lighting_label


LAT = 41.8781
LON = -87.6298
WINDOW = 30  # minutes


def _utc(hour, minute=0):
    return datetime(2026, 4, 30, hour, minute, tzinfo=timezone.utc)


def _make_sun(sunrise_hour=11, sunset_hour=23):
    """Return mock sun dict with UTC times (Chicago ~UTC-5 in CDT, so 6am local = 11am UTC)."""
    return {
        "sunrise": _utc(sunrise_hour),
        "sunset": _utc(sunset_hour),
    }


def test_label_day():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        label = get_lighting_label(_utc(14), LAT, LON, WINDOW)
    assert label == "day"


def test_label_night_before_sunrise():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        label = get_lighting_label(_utc(5), LAT, LON, WINDOW)
    assert label == "night"


def test_label_night_after_sunset():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        label = get_lighting_label(_utc(23, 45), LAT, LON, WINDOW)
    assert label == "night"


def test_label_sunrise_window():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        # 15 minutes before sunrise = inside window
        label = get_lighting_label(_utc(10, 45), LAT, LON, WINDOW)
    assert label == "sunrise"


def test_label_sunset_window():
    sun = _make_sun(sunrise_hour=11, sunset_hour=23)
    with patch("src.lighting.sun", return_value=sun):
        # 10 minutes after sunset = inside window
        label = get_lighting_label(_utc(23, 10), LAT, LON, WINDOW)
    assert label == "sunset"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_lighting.py -v
```
Expected: `ImportError` for `src.lighting`

- [ ] **Step 3: Implement `src/lighting.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from astral import LocationInfo
from astral.sun import sun


def get_lighting_label(
    dt: datetime,
    latitude: float,
    longitude: float,
    window_minutes: int,
) -> str:
    """Return 'day', 'night', 'sunrise', or 'sunset' for a given UTC datetime."""
    location = LocationInfo(latitude=latitude, longitude=longitude)
    s = sun(location.observer, date=dt.date(), tzinfo=timezone.utc)
    sunrise = s["sunrise"]
    sunset = s["sunset"]
    window = timedelta(minutes=window_minutes)

    if abs(dt - sunrise) <= window:
        return "sunrise"
    if abs(dt - sunset) <= window:
        return "sunset"
    if sunrise + window < dt < sunset - window:
        return "day"
    return "night"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_lighting.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/lighting.py tests/test_lighting.py
git commit -m "feat: lighting label calculation using astral"
```

---

## Task 4: Camera Module

**Files:**
- Create: `src/camera.py`
- Create: `tests/test_camera.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_camera.py
import pytest
from unittest.mock import patch, MagicMock
from src.camera import CameraClient, CameraError


BASE = "http://192.168.1.100"
USER = "admin"
PASS = "secret"


def _client():
    return CameraClient(ip="192.168.1.100", username=USER, password=PASS)


def _preset_response(presets):
    mock = MagicMock()
    mock.json.return_value = [
        {"code": 0, "value": {"PtzPreset": presets}}
    ]
    mock.raise_for_status = MagicMock()
    return mock


def test_get_preset_id_by_name():
    client = _client()
    presets = [
        {"id": 1, "name": "home"},
        {"id": 3, "name": "full garden"},
    ]
    with patch("src.camera.requests.get", return_value=_preset_response(presets)) as mock_get:
        preset_id = client.get_preset_id("full garden")
    assert preset_id == 3


def test_get_preset_id_not_found_raises():
    client = _client()
    presets = [{"id": 1, "name": "home"}]
    with patch("src.camera.requests.get", return_value=_preset_response(presets)):
        with pytest.raises(CameraError, match="Preset 'missing' not found"):
            client.get_preset_id("missing")


def test_get_preset_id_not_found_lists_available():
    client = _client()
    presets = [{"id": 1, "name": "home"}, {"id": 2, "name": "driveway"}]
    with patch("src.camera.requests.get", return_value=_preset_response(presets)):
        with pytest.raises(CameraError, match="home.*driveway"):
            client.get_preset_id("missing")


def test_goto_preset_sends_correct_request():
    client = _client()
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"code": 0}]
    mock_resp.raise_for_status = MagicMock()
    with patch("src.camera.requests.post", return_value=mock_resp) as mock_post:
        client.goto_preset(3)
    call_kwargs = mock_post.call_args
    assert "GotoPreset" in str(call_kwargs)


def test_fetch_snapshot_returns_bytes():
    client = _client()
    mock_resp = MagicMock()
    mock_resp.content = b"\xff\xd8\xff"  # JPEG magic bytes
    mock_resp.raise_for_status = MagicMock()
    with patch("src.camera.requests.get", return_value=mock_resp):
        data = client.fetch_snapshot()
    assert data == b"\xff\xd8\xff"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_camera.py -v
```
Expected: `ImportError` for `src.camera`

- [ ] **Step 3: Implement `src/camera.py`**

```python
from __future__ import annotations
import requests


class CameraError(Exception):
    pass


class CameraClient:
    def __init__(self, ip: str, username: str, password: str, timeout: int = 10):
        self._base = f"http://{ip}"
        self._auth = {"user": username, "password": password}
        self._timeout = timeout

    def _params(self, **extra) -> dict:
        return {**self._auth, **extra}

    def get_preset_id(self, name: str) -> int:
        resp = requests.get(
            f"{self._base}/api.cgi",
            params={**self._params(), "cmd": "GetPtzPreset", "channel": 0},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        presets = resp.json()[0]["value"]["PtzPreset"]
        for p in presets:
            if p["name"].lower() == name.lower():
                return int(p["id"])
        available = ", ".join(p["name"] for p in presets)
        raise CameraError(
            f"Preset '{name}' not found. Available presets: {available}"
        )

    def goto_preset(self, preset_id: int) -> None:
        resp = requests.post(
            f"{self._base}/api.cgi",
            params=self._params(),
            json=[{"cmd": "GotoPreset", "param": {"channel": 0, "id": preset_id}}],
            timeout=self._timeout,
        )
        resp.raise_for_status()
        code = resp.json()[0].get("code", -1)
        if code != 0:
            raise CameraError(f"GotoPreset returned error code {code}")

    def fetch_snapshot(self) -> bytes:
        import random
        import string
        rs = "".join(random.choices(string.ascii_lowercase, k=8))
        resp = requests.get(
            f"{self._base}/cgi-bin/api.cgi",
            params={**self._params(), "cmd": "Snap", "channel": 0, "rs": rs},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_camera.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/camera.py tests/test_camera.py
git commit -m "feat: Reolink HTTP API client (presets, PTZ move, snapshot)"
```

---

## Task 5: Capture Module

**Files:**
- Create: `src/capture.py`
- Create: `tests/test_capture.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_capture.py
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone
from pathlib import Path
from src.capture import build_snapshot_path, run_capture
from src.config import Config


def _cfg(tmp_path):
    return Config(
        camera_ip="192.168.1.100",
        camera_username="admin",
        camera_password="secret",
        preset_name="full garden",
        ptz_settle_delay=0,
        snapshot_interval=15,
        snapshot_24_7=True,
        latitude=41.8781,
        longitude=-87.6298,
        sunrise_sunset_window=30,
        timelapse_include_night=True,
        timelapse_fps=24,
        snapshot_dir=str(tmp_path / "snapshots"),
        timelapse_dir=str(tmp_path / "timelapse"),
    )


def test_build_snapshot_path_format(tmp_path):
    cfg = _cfg(tmp_path)
    dt = datetime(2026, 4, 30, 14, 32, 0, tzinfo=timezone.utc)
    path = build_snapshot_path(cfg, dt, "day")
    assert path.name == "full_garden_2026-04-30_14-32-00_day.jpg"
    assert path.parent.name == "2026-04-30"


def test_build_snapshot_path_spaces_replaced(tmp_path):
    cfg = _cfg(tmp_path)
    dt = datetime(2026, 4, 30, 6, 0, 0, tzinfo=timezone.utc)
    path = build_snapshot_path(cfg, dt, "sunrise")
    assert " " not in path.name


def test_run_capture_saves_file(tmp_path):
    cfg = _cfg(tmp_path)
    mock_client = MagicMock()
    mock_client.get_preset_id.return_value = 3
    mock_client.fetch_snapshot.return_value = b"\xff\xd8\xff\xe0"
    dt = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.capture.get_lighting_label", return_value="day"):
        path = run_capture(cfg, mock_client, dt)

    assert path.exists()
    assert path.read_bytes() == b"\xff\xd8\xff\xe0"


def test_run_capture_calls_goto_preset(tmp_path):
    cfg = _cfg(tmp_path)
    mock_client = MagicMock()
    mock_client.get_preset_id.return_value = 5
    mock_client.fetch_snapshot.return_value = b"\xff\xd8"
    dt = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)

    with patch("src.capture.get_lighting_label", return_value="day"):
        run_capture(cfg, mock_client, dt)

    mock_client.goto_preset.assert_called_once_with(5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_capture.py -v
```
Expected: `ImportError` for `src.capture`

- [ ] **Step 3: Implement `src/capture.py`**

```python
from __future__ import annotations
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from src.config import Config
from src.camera import CameraClient
from src.lighting import get_lighting_label

log = logging.getLogger(__name__)


def build_snapshot_path(cfg: Config, dt: datetime, label: str) -> Path:
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H-%M-%S")
    preset_slug = cfg.preset_name.replace(" ", "_")
    filename = f"{preset_slug}_{date_str}_{time_str}_{label}.jpg"
    directory = Path(cfg.snapshot_dir) / date_str
    return directory / filename


def run_capture(cfg: Config, client: CameraClient, dt: datetime | None = None) -> Path:
    if dt is None:
        dt = datetime.now(tz=timezone.utc)

    label = get_lighting_label(dt, cfg.latitude, cfg.longitude, cfg.sunrise_sunset_window)

    preset_id = client.get_preset_id(cfg.preset_name)
    client.goto_preset(preset_id)

    if cfg.ptz_settle_delay > 0:
        time.sleep(cfg.ptz_settle_delay)

    image_bytes = client.fetch_snapshot()

    path = build_snapshot_path(cfg, dt, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    log.info("Saved snapshot: %s", path)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_capture.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/capture.py tests/test_capture.py
git commit -m "feat: capture module — PTZ move, label, save snapshot"
```

---

## Task 6: Timelapse Module

**Files:**
- Create: `src/timelapse.py`
- Create: `tests/test_timelapse.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_timelapse.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.timelapse import collect_snapshots, build_timelapse


def _make_snapshots(tmp_path, names):
    d = tmp_path / "2026-04-30"
    d.mkdir(parents=True)
    paths = []
    for name in names:
        p = d / name
        p.write_bytes(b"\xff\xd8")
        paths.append(p)
    return paths


def test_collect_snapshots_returns_sorted(tmp_path):
    names = [
        "garden_2026-04-30_14-00-00_day.jpg",
        "garden_2026-04-30_06-00-00_sunrise.jpg",
        "garden_2026-04-30_22-00-00_night.jpg",
    ]
    _make_snapshots(tmp_path, names)
    result = collect_snapshots(tmp_path / "2026-04-30", include_night=True)
    assert [p.name for p in result] == sorted(names)


def test_collect_snapshots_excludes_night(tmp_path):
    names = [
        "garden_2026-04-30_10-00-00_day.jpg",
        "garden_2026-04-30_22-00-00_night.jpg",
    ]
    _make_snapshots(tmp_path, names)
    result = collect_snapshots(tmp_path / "2026-04-30", include_night=False)
    assert len(result) == 1
    assert "night" not in result[0].name


def test_collect_snapshots_empty_dir(tmp_path):
    d = tmp_path / "2026-04-30"
    d.mkdir()
    result = collect_snapshots(d, include_night=True)
    assert result == []


def test_build_timelapse_calls_ffmpeg(tmp_path):
    names = ["garden_2026-04-30_10-00-00_day.jpg"]
    snapshots = _make_snapshots(tmp_path, names)
    output = tmp_path / "timelapse_2026-04-30.mp4"

    with patch("src.timelapse.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        build_timelapse(snapshots, output, fps=24)

    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert "ffmpeg" in cmd[0]
    assert str(output) in cmd


def test_build_timelapse_no_snapshots_skips(tmp_path):
    output = tmp_path / "timelapse.mp4"
    with patch("src.timelapse.subprocess.run") as mock_run:
        build_timelapse([], output, fps=24)
    mock_run.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_timelapse.py -v
```
Expected: `ImportError` for `src.timelapse`

- [ ] **Step 3: Implement `src/timelapse.py`**

```python
from __future__ import annotations
import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def collect_snapshots(snapshot_dir: Path, include_night: bool) -> list[Path]:
    if not snapshot_dir.exists():
        return []
    files = sorted(snapshot_dir.glob("*.jpg"))
    if not include_night:
        files = [f for f in files if "_night" not in f.name]
    return files


def build_timelapse(snapshots: list[Path], output: Path, fps: int) -> None:
    if not snapshots:
        log.warning("No snapshots available, skipping timelapse build")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_suffix(".tmp.mp4")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for snap in snapshots:
            f.write(f"file '{snap.resolve()}'\n")
            f.write(f"duration {1/fps:.6f}\n")
        list_file = f.name

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(tmp_output),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.error("ffmpeg failed:\n%s", result.stderr)
            tmp_output.unlink(missing_ok=True)
            return
        tmp_output.replace(output)
        log.info("Timelapse saved: %s", output)
    finally:
        Path(list_file).unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_timelapse.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/timelapse.py tests/test_timelapse.py
git commit -m "feat: timelapse builder using ffmpeg concat"
```

---

## Task 7: Scheduler (Entry Point)

**Files:**
- Create: `src/scheduler.py`

No unit tests for the scheduler — it's a thin orchestration loop. Integration testing is done by running the container.

- [ ] **Step 1: Implement `src/scheduler.py`**

```python
from __future__ import annotations
import logging
import signal
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from src.config import Config, ConfigError
from src.camera import CameraClient, CameraError
from src.capture import run_capture
from src.timelapse import collect_snapshots, build_timelapse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("scheduler")

_shutdown = False


def _handle_sigterm(signum, frame):
    global _shutdown
    log.info("SIGTERM received, shutting down after current cycle")
    _shutdown = True


def _rebuild_timelapse(cfg: Config, date_str: str) -> None:
    snapshot_dir = Path(cfg.snapshot_dir) / date_str
    snapshots = collect_snapshots(snapshot_dir, include_night=cfg.timelapse_include_night)
    output = Path(cfg.timelapse_dir) / f"timelapse_{date_str}.mp4"
    try:
        build_timelapse(snapshots, output, fps=cfg.timelapse_fps)
    except Exception as exc:
        log.error("Timelapse build failed: %s", exc)


def run(cfg: Config) -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    client = CameraClient(
        ip=cfg.camera_ip,
        username=cfg.camera_username,
        password=cfg.camera_password,
    )
    interval = timedelta(minutes=cfg.snapshot_interval)
    current_date = datetime.now(tz=timezone.utc).date()

    log.info("Scheduler started. Interval: %d min", cfg.snapshot_interval)

    while not _shutdown:
        now = datetime.now(tz=timezone.utc)

        # Midnight rotation
        if now.date() != current_date:
            log.info("New day — finalizing timelapse for %s", current_date)
            _rebuild_timelapse(cfg, str(current_date))
            current_date = now.date()

        # Skip night captures if not 24/7
        if not cfg.snapshot_24_7:
            from src.lighting import get_lighting_label
            label = get_lighting_label(now, cfg.latitude, cfg.longitude, cfg.sunrise_sunset_window)
            if label == "night":
                log.debug("Night — skipping capture (SNAPSHOT_24_7=false)")
                time.sleep(60)
                continue

        try:
            run_capture(cfg, client, now)
            _rebuild_timelapse(cfg, str(now.date()))
        except CameraError as exc:
            log.error("Camera error: %s", exc)
        except Exception as exc:
            log.error("Unexpected error during capture: %s", exc)

        if _shutdown:
            break

        next_tick = now + interval
        sleep_secs = (next_tick - datetime.now(tz=timezone.utc)).total_seconds()
        if sleep_secs > 0:
            log.info("Next capture in %.0f seconds", sleep_secs)
            time.sleep(sleep_secs)

    log.info("Scheduler stopped")


if __name__ == "__main__":
    load_dotenv("/app/.env")
    try:
        cfg = Config.from_env()
    except ConfigError as exc:
        log.critical("Configuration error: %s", exc)
        raise SystemExit(1)
    run(cfg)
```

- [ ] **Step 2: Commit**

```bash
git add src/scheduler.py
git commit -m "feat: scheduler loop with SIGTERM handling and midnight rotation"
```

---

## Task 8: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "-m", "src.scheduler"]
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  timelapse:
    build: .
    restart: unless-stopped
    volumes:
      - /data/timelapse/snapshots:/data/snapshots
      - /data/timelapse/timelapse:/data/timelapse
      - /data/timelapse/.env:/app/.env:ro
    environment:
      - TZ=America/Chicago
```

- [ ] **Step 3: Build the image to verify it works**

```bash
docker compose build
```
Expected: Build completes with no errors. ffmpeg and Python packages installed.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Docker image and compose config"
```

---

## Task 9: Full Test Suite Pass & README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Run full test suite**

```bash
pip install -r requirements-dev.txt -r requirements.txt
pytest tests/ -v
```
Expected: All tests PASS (no failures, no errors)

- [ ] **Step 2: Create `README.md`**

```markdown
# Reolink PTZ Timelapse

Dockerized app that periodically moves a Reolink PTZ camera to a named preset, captures a high-resolution snapshot labeled with lighting conditions, and builds a daily timelapse video.

## Setup

1. Copy `.env.example` to `.env` and fill in your values:
   ```
   cp .env.example .env
   ```

2. Build and start:
   ```
   docker compose up -d
   ```

3. View logs:
   ```
   docker compose logs -f
   ```

## Output

- Snapshots: `/data/timelapse/snapshots/YYYY-MM-DD/`
- Timelapse: `/data/timelapse/timelapse/timelapse_YYYY-MM-DD.mp4`

## Configuration

See `.env.example` for all options with descriptions.

## Notes

- Reolink firmware versions vary. If snapshots fail, check that your camera's HTTP API is enabled in the Reolink app under **Device Settings → Network → Advanced**.
- The snapshot URL format (`/cgi-bin/api.cgi?cmd=Snap`) works on most Reolink NVR and standalone camera firmware. If it returns an error, try `/api.cgi?cmd=Snap` instead.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and configuration notes"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Config ✓, lighting labels ✓, camera API ✓, capture orchestration ✓, timelapse build ✓, scheduler loop ✓, midnight rotation ✓, SIGTERM ✓, Docker ✓, error handling (camera unreachable, preset not found, PTZ fail, ffmpeg fail) ✓
- [x] **Placeholders:** None — all steps have complete code
- [x] **Type consistency:** `Config` dataclass used consistently across all modules; `CameraClient` passed as parameter; `run_capture` returns `Path`; `collect_snapshots` returns `list[Path]`; `build_timelapse` takes `list[Path]`
