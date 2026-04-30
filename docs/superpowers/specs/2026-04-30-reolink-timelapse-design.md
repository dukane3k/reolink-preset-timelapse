# Reolink PTZ Timelapse — Design Spec

**Date:** 2026-04-30  
**Status:** Approved

---

## Overview

A Dockerized Python application that periodically moves a Reolink PTZ camera to a named preset, captures a high-quality snapshot, labels it with a lighting condition (day/night/sunrise/sunset), and assembles a daily timelapse video from the collected snapshots.

---

## Architecture

Three Python modules inside a single Docker container:

| Module | Role |
|---|---|
| `capture.py` | One-shot: move PTZ to named preset, wait for settle, save timestamped snapshot with lighting label |
| `scheduler.py` | Long-running entry point: runs capture loop on configured interval, triggers timelapse build at midnight, handles SIGTERM gracefully |
| `timelapse.py` | Builds (or rebuilds) the daily timelapse MP4 from the current day's snapshots using ffmpeg |

---

## Directory Structure (host volume)

```
/data/timelapse/
├── snapshots/
│   └── YYYY-MM-DD/
│       ├── full_garden_2026-04-30_06-12-00_sunrise.jpg
│       ├── full_garden_2026-04-30_10-45-00_day.jpg
│       ├── full_garden_2026-04-30_21-30-00_night.jpg
│       └── ...
├── timelapse/
│   └── timelapse_2026-04-30.mp4   # rebuilt throughout day, finalized at midnight
└── .env
```

---

## Lighting Labels

Calculated per-snapshot using the `astral` Python library with configured lat/long:

- `sunrise` — within `SUNRISE_SUNSET_WINDOW` minutes before/after actual sunrise
- `sunset` — within `SUNRISE_SUNSET_WINDOW` minutes before/after actual sunset
- `day` — between sunrise window end and sunset window start
- `night` — all other times

---

## Configuration (`.env`)

```env
# Camera
CAMERA_IP=192.168.1.100
CAMERA_USERNAME=admin
CAMERA_PASSWORD=secret
CAMERA_PRESET_NAME=full garden
PTZ_SETTLE_DELAY=4              # seconds to wait after PTZ move before snapshot

# Scheduling
SNAPSHOT_INTERVAL=15            # minutes between snapshots
SNAPSHOT_24_7=true              # false = only shoot during daylight hours

# Location (for sunrise/sunset calculation)
LATITUDE=41.8781
LONGITUDE=-87.6298
SUNRISE_SUNSET_WINDOW=30        # minutes around sunrise/sunset to apply those labels

# Timelapse
TIMELAPSE_INCLUDE_NIGHT=true    # false = exclude night-labeled snapshots from video
TIMELAPSE_FPS=24                # frames per second in output video

# Output
SNAPSHOT_DIR=/data/snapshots
TIMELAPSE_DIR=/data/timelapse
```

---

## Camera Integration

- Protocol: Reolink HTTP CGI API (local network, no cloud)
- Auth: username/password query params
- PTZ preset lookup: `GET /api.cgi?cmd=GetPtzPreset` → find preset by name → extract preset ID
- PTZ move: `POST /api.cgi?cmd=GotoPreset` with preset ID
- Snapshot: `GET /cgi-bin/api.cgi?cmd=Snap&channel=0&rs=...&user=...&password=...` (main stream)
- All HTTP calls use the `requests` library with a short timeout

---

## Scheduler Behavior

- On startup: immediately attempt one capture
- Loop: sleep until next interval tick, then capture
- At midnight: finalize today's timelapse, rotate to new date
- Timelapse rebuild: also triggered after each capture (so a current video is always available)
- Shutdown: catches SIGTERM, finishes current capture/build, exits cleanly

---

## Docker Setup

**`Dockerfile`:** `python:3.12-slim` base, installs `ffmpeg` via apt, installs Python deps from `requirements.txt`, entry point is `scheduler.py`.

**`requirements.txt`:**
```
requests
astral
python-dotenv
```

**`docker-compose.yml`:**
```yaml
services:
  timelapse:
    build: .
    restart: unless-stopped
    volumes:
      - /data/timelapse/snapshots:/data/snapshots
      - /data/timelapse/timelapse:/data/timelapse
      - /data/timelapse/.env:/app/.env
    environment:
      - TZ=America/Chicago
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Camera unreachable | Log error, skip snapshot, continue loop |
| Preset name not found | Log error + list available presets, skip snapshot |
| PTZ move fails | Log error, still attempt snapshot |
| ffmpeg timelapse build fails | Log error, preserve previous timelapse file |
| Disk space exhaustion | No active check — handled at host level |

---

## Out of Scope

- Web UI or live preview
- Multiple cameras or presets per run
- Disk space monitoring
- Cloud upload
