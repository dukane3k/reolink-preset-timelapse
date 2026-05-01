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

## Manual Capture

Trigger an immediate snapshot outside the normal schedule:

```bash
docker exec reolink-preset-timelapse python -m src.capture_now
```

Uses all the same settings as scheduled captures (preset, OSD, home preset, lighting label). Prints the saved file path on success.

## Permanent Timelapse

Build a single timelapse video from all snapshots ever taken:

```bash
docker exec reolink-preset-timelapse python -m src.build_permanent
```

The output is saved to `TIMELAPSE_DIR/permanent/timelapse_permanent_YYYY-MM-DD_HH-MM-SS.mp4`. Respects `TIMELAPSE_INCLUDE_NIGHT`. Each run produces a new timestamped file.

## Timelapse Retention

Daily timelapse MP4s are automatically pruned at midnight to prevent unbounded disk usage:

- Files within the last `TIMELAPSE_RETENTION_DAYS` days (default: 7) are always kept
- Beyond that window, one file every `TIMELAPSE_ARCHIVE_EVERY` days (default: 7) is kept as an archive
- Everything else is deleted

Example with defaults: after 30 days you'd have 7 daily files + ~3 weekly archives.

## Configuration

See `.env.example` for all options with descriptions.

## Notes

- Reolink firmware versions vary. If snapshots fail, check that your camera's HTTP API is enabled in the Reolink app under **Device Settings → Network → Advanced**.
- The snapshot URL format (`/cgi-bin/api.cgi?cmd=Snap`) works on most Reolink NVR and standalone camera firmware. If it returns an error, try `/api.cgi?cmd=Snap` instead.
- Camera credentials are transmitted as URL query parameters (per the Reolink API design). Keep the camera on a trusted LAN segment and do not expose it to untrusted networks.
