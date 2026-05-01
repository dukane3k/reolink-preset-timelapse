from __future__ import annotations
import logging
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})")


def collect_snapshots(snapshot_dir: Path, include_night: bool) -> list[Path]:
    if not snapshot_dir.exists():
        return []
    files = sorted(snapshot_dir.glob("*.jpg"))
    if not include_night:
        files = [f for f in files if "_night" not in f.name]
    return files


def _parse_snapshot_dt(path: Path) -> datetime | None:
    m = _TIMESTAMP_RE.search(path.stem)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H-%M-%S")
    except ValueError:
        return None


def _srt_timestamp(td: timedelta) -> str:
    total = int(td.total_seconds() * 1000)
    ms = total % 1000
    s = (total // 1000) % 60
    m = (total // 60000) % 60
    h = total // 3600000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(snapshots: list[Path], fps: int, every: int = 1) -> str:
    frame_duration = timedelta(seconds=1 / fps)
    index = 1
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
        for i, snap in enumerate(snapshots):
            if i % every != 0:
                continue
            start = frame_duration * i
            # subtitle spans until the next labelled frame or end of current frame
            end = frame_duration * min(i + every, len(snapshots))
            dt = _parse_snapshot_dt(snap)
            label = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else snap.stem
            f.write(f"{index}\n")
            f.write(f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n")
            f.write(f"{label}\n\n")
            index += 1
        return f.name


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


def build_timelapse(
    snapshots: list[Path],
    output: Path,
    fps: int,
    stabilize: bool = False,
    subtitles: bool = True,
    subtitle_every: int = 1,
) -> None:
    if not snapshots:
        log.warning("No snapshots available, skipping timelapse build")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output.with_suffix(".tmp.mp4")
    list_file = _write_concat_list(snapshots, fps)
    srt_file = _write_srt(snapshots, fps, every=subtitle_every) if subtitles else None

    try:
        if stabilize:
            _build_stabilized(list_file, srt_file, tmp_output, output)
        else:
            _build_simple(list_file, srt_file, tmp_output, output)
    finally:
        Path(list_file).unlink(missing_ok=True)
        if srt_file:
            Path(srt_file).unlink(missing_ok=True)


def _build_simple(list_file: str, srt_file: str | None, tmp_output: Path, output: Path) -> None:
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file]
    if srt_file:
        cmd += ["-i", srt_file]
    cmd += ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if srt_file:
        cmd += ["-c:s", "mov_text", "-map", "0:v", "-map", "1:s"]
    cmd.append(str(tmp_output))

    ok = _run(cmd, "ffmpeg")
    if ok:
        tmp_output.replace(output)
        log.info("Timelapse saved: %s", output)
    else:
        tmp_output.unlink(missing_ok=True)


def _build_stabilized(list_file: str, srt_file: str | None, tmp_output: Path, output: Path) -> None:
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
            _build_simple(list_file, srt_file, tmp_output, output)
            return

        # Pass 2: apply stabilization and optionally embed subtitles
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file]
        if srt_file:
            cmd += ["-i", srt_file]
        cmd += [
            "-vf", (
                f"vidstabtransform=input={transforms}:smoothing=30:crop=black,"
                "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            ),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
        ]
        if srt_file:
            cmd += ["-c:s", "mov_text", "-map", "0:v", "-map", "1:s"]
        cmd.append(str(tmp_output))

        ok = _run(cmd, "vidstabtransform")
        if ok:
            tmp_output.replace(output)
            log.info("Stabilized timelapse saved: %s", output)
        else:
            tmp_output.unlink(missing_ok=True)
    finally:
        transforms.unlink(missing_ok=True)
