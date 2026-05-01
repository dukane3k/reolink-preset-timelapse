from __future__ import annotations
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
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


def _ass_timestamp(td: timedelta) -> str:
    total = int(td.total_seconds() * 100)
    cs = total % 100
    s = (total // 100) % 60
    m = (total // 6000) % 60
    h = total // 360000
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _write_burnin_ass(
    snapshots: list[Path],
    fps: int,
    every_minutes: int,
    display_seconds: float = 5.0,
    fade_seconds: float = 1.0,
) -> str:
    """Write an ASS subtitle file with bottom-right timestamps that fade out after display_seconds."""
    frame_duration = 1.0 / fps
    fade_ms = int(fade_seconds * 1000)

    # ASS header — alignment=3 is bottom-right in numpad layout
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # white text, no outline, soft drop shadow, bottom-right, letter spacing 3
        "Style: Burnin,Liberation Sans,56,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,"
        "0,0,0,0,100,100,3,0,0,0,3,3,10,10,20,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    # Parse all snapshot datetimes upfront
    dts = [_parse_snapshot_dt(s) for s in snapshots]
    first_dt = next((d for d in dts if d is not None), None)
    if first_dt is None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8") as f:
            f.write(header)
            return f.name

    # Collect emit frames first so we can cap each entry at the next one's start
    emit_frames: list[tuple[int, str]] = []
    last_bucket = -1
    for i, (snap, dt) in enumerate(zip(snapshots, dts)):
        if dt is None:
            continue
        elapsed_minutes = (dt - first_dt).total_seconds() / 60
        bucket = int(elapsed_minutes) // every_minutes
        if bucket == last_bucket:
            continue
        last_bucket = bucket
        label = dt.strftime("%m/%d/%Y %H:%M")
        emit_frames.append((i, label))

    lines = []
    for idx, (i, label) in enumerate(emit_frames):
        start_sec = i * frame_duration
        # End no later than the next entry's start to prevent stacking
        if idx + 1 < len(emit_frames):
            next_start_sec = emit_frames[idx + 1][0] * frame_duration
            end_sec = min(start_sec + display_seconds, next_start_sec)
        else:
            end_sec = start_sec + display_seconds
        fade_out_ms = min(fade_ms, int((end_sec - start_sec) * 1000))
        start = _ass_timestamp(timedelta(seconds=start_sec))
        end = _ass_timestamp(timedelta(seconds=end_sec))
        text = f"{{\\fad(0,{fade_out_ms})}}{label.upper()}"
        lines.append(f"Dialogue: 0,{start},{end},Burnin,,0,0,0,,{text}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines))
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
    align: bool = False,
    stabilize: bool = False,
    stabilize_crop: int = 5,
    stabilize_smoothing: int = 5,
    stabilize_shakiness: int = 5,
    subtitles: bool = True,
    subtitle_every: int = 1,
    burnin: bool = False,
    burnin_every_minutes: int = 30,
) -> None:
    if not snapshots:
        log.warning("No snapshots available, skipping timelapse build")
        return

    output.parent.mkdir(parents=True, exist_ok=True)

    align_dir = None
    try:
        if align:
            from src.alignment import align_snapshots
            align_dir = Path(tempfile.mkdtemp(prefix="timelapse_align_"))
            log.info("Aligning %d frames to reference...", len(snapshots))
            snapshots = align_snapshots(snapshots, align_dir)

        tmp_output = output.with_suffix(".tmp.mp4")
        list_file = _write_concat_list(snapshots, fps)
        srt_file = _write_srt(snapshots, fps, every=subtitle_every) if subtitles else None
        ass_file = _write_burnin_ass(snapshots, fps, every_minutes=burnin_every_minutes) if burnin else None

        try:
            if stabilize:
                _build_stabilized(list_file, srt_file, ass_file, tmp_output, output, stabilize_crop, stabilize_smoothing, stabilize_shakiness)
            else:
                _build_simple(list_file, srt_file, ass_file, tmp_output, output)
        finally:
            Path(list_file).unlink(missing_ok=True)
            if srt_file:
                Path(srt_file).unlink(missing_ok=True)
            if ass_file:
                Path(ass_file).unlink(missing_ok=True)
    finally:
        if align_dir and align_dir.exists():
            shutil.rmtree(align_dir, ignore_errors=True)


def _video_filters(ass_file: str | None) -> str:
    filters = []
    if ass_file:
        filters.append(f"ass={ass_file}")
    filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
    return ",".join(filters)


def _build_simple(list_file: str, srt_file: str | None, ass_file: str | None, tmp_output: Path, output: Path) -> None:
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file]
    if srt_file:
        cmd += ["-i", srt_file]
    cmd += ["-vf", _video_filters(ass_file), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if srt_file:
        cmd += ["-c:s", "mov_text", "-map", "0:v", "-map", "1:s"]
    cmd.append(str(tmp_output))

    ok = _run(cmd, "ffmpeg")
    if ok:
        tmp_output.replace(output)
        log.info("Timelapse saved: %s", output)
    else:
        tmp_output.unlink(missing_ok=True)


def _build_stabilized(list_file: str, srt_file: str | None, ass_file: str | None, tmp_output: Path, output: Path, stabilize_crop: int = 5, stabilize_smoothing: int = 5, stabilize_shakiness: int = 5) -> None:
    transforms = tmp_output.with_suffix(".trf")
    try:
        # Pass 1: analyze motion
        ok = _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-vf", f"vidstabdetect=result={transforms}:shakiness={stabilize_shakiness}:accuracy=15",
            "-f", "null", "-",
        ], "vidstabdetect")
        if not ok:
            log.warning("Stabilization analysis failed, falling back to unstabilized")
            _build_simple(list_file, srt_file, ass_file, tmp_output, output)
            return

        # Pass 2: apply stabilization with auto-zoom to keep center clean, then trim any remaining edges
        # optzoom=2 calculates the zoom needed to fill the frame without black borders,
        # concentrating any residual distortion at the edges rather than the center.
        stabilize_vf = (
            f"vidstabtransform=input={transforms}:smoothing={stabilize_smoothing}"
            f":crop=black:optzoom=2:zoom=0"
        )
        crop_filter = f"crop=iw*{(100-stabilize_crop*2)/100}:ih*{(100-stabilize_crop*2)/100}" if stabilize_crop > 0 else None
        filters = [stabilize_vf]
        if crop_filter:
            filters.append(crop_filter)
        if ass_file:
            filters.append(f"ass={ass_file}")
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
        vf = ",".join(filters)

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file]
        if srt_file:
            cmd += ["-i", srt_file]
        cmd += ["-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p"]
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
