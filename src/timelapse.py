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


def _write_concat_list(snapshots: list[Path], fps: int) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for snap in snapshots:
            f.write(f"file '{snap.resolve()}'\n")
            f.write(f"duration {1/fps:.6f}\n")
        return f.name


def _run(cmd: list[str], label: str) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("%s failed:\n%s", label, result.stderr)
        return False
    return True


def build_timelapse(snapshots: list[Path], output: Path, fps: int, stabilize: bool = False) -> None:
    if not snapshots:
        log.warning("No snapshots available, skipping timelapse build")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_suffix(".tmp.mp4")
    list_file = _write_concat_list(snapshots, fps)

    try:
        if stabilize:
            _build_stabilized(list_file, tmp_output, output)
        else:
            _build_simple(list_file, tmp_output, output)
    finally:
        Path(list_file).unlink(missing_ok=True)


def _build_simple(list_file: str, tmp_output: Path, output: Path) -> None:
    ok = _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(tmp_output),
    ], "ffmpeg")
    if ok:
        tmp_output.replace(output)
        log.info("Timelapse saved: %s", output)
    else:
        tmp_output.unlink(missing_ok=True)


def _build_stabilized(list_file: str, tmp_output: Path, output: Path) -> None:
    transforms = tmp_output.with_suffix(".trf")
    try:
        # Pass 1: analyze motion
        ok = _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-vf", f"vidstabdetect=result={transforms}:shakiness=10:accuracy=15",
            "-f", "null", "-",
        ], "vidstabdetect")
        if not ok:
            log.warning("Stabilization analysis failed, falling back to unstabilized")
            _build_simple(list_file, tmp_output, output)
            return

        # Pass 2: apply stabilization
        ok = _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-vf", (
                f"vidstabtransform=input={transforms}:smoothing=30:crop=black,"
                "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(tmp_output),
        ], "vidstabtransform")
        if ok:
            tmp_output.replace(output)
            log.info("Stabilized timelapse saved: %s", output)
        else:
            tmp_output.unlink(missing_ok=True)
    finally:
        transforms.unlink(missing_ok=True)
