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
                str(output),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.error("ffmpeg failed:\n%s", result.stderr)
            output.unlink(missing_ok=True)
            return
        log.info("Timelapse saved: %s", output)
    finally:
        Path(list_file).unlink(missing_ok=True)
