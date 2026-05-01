import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import timedelta
from src.timelapse import collect_snapshots, build_timelapse, _parse_snapshot_dt, _srt_timestamp, _write_srt


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


def test_parse_snapshot_dt(tmp_path):
    p = tmp_path / "garden_2026-04-30_19-35-00_day.jpg"
    dt = _parse_snapshot_dt(p)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 30
    assert dt.hour == 19
    assert dt.minute == 35
    assert dt.second == 0


def test_srt_timestamp_format():
    assert _srt_timestamp(timedelta(0)) == "00:00:00,000"
    assert _srt_timestamp(timedelta(hours=1, minutes=2, seconds=3, milliseconds=456)) == "01:02:03,456"


def test_write_srt_contains_timestamps(tmp_path):
    names = [
        "garden_2026-04-30_10-00-00_day.jpg",
        "garden_2026-04-30_10-30-00_day.jpg",
    ]
    snapshots = _make_snapshots(tmp_path, names)
    srt_path = _write_srt(snapshots, fps=24)
    content = Path(srt_path).read_text()
    Path(srt_path).unlink()
    assert "2026-04-30 10:00:00" in content
    assert "2026-04-30 10:30:00" in content


def test_build_timelapse_calls_ffmpeg(tmp_path):
    names = ["garden_2026-04-30_10-00-00_day.jpg"]
    snapshots = _make_snapshots(tmp_path, names)
    output = tmp_path / "timelapse_2026-04-30.mp4"

    def mock_ffmpeg_success(cmd, **kwargs):
        tmp_output = output.with_suffix(".tmp.mp4")
        tmp_output.write_bytes(b"fake video data")
        return MagicMock(returncode=0)

    with patch("src.timelapse.subprocess.run") as mock_run:
        mock_run.side_effect = mock_ffmpeg_success
        build_timelapse(snapshots, output, fps=24, stabilize=False)

    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert "ffmpeg" in cmd[0]
    assert str(output.with_suffix(".tmp.mp4")) in cmd
    assert "mov_text" in cmd


def test_build_timelapse_no_snapshots_skips(tmp_path):
    output = tmp_path / "timelapse.mp4"
    with patch("src.timelapse.subprocess.run") as mock_run:
        build_timelapse([], output, fps=24)
    mock_run.assert_not_called()


def test_build_timelapse_stabilized_runs_two_passes(tmp_path):
    names = ["garden_2026-04-30_10-00-00_day.jpg"]
    snapshots = _make_snapshots(tmp_path, names)
    output = tmp_path / "timelapse_2026-04-30.mp4"

    call_count = 0

    def mock_ffmpeg_success(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            tmp_output = output.with_suffix(".tmp.mp4")
            tmp_output.write_bytes(b"fake stabilized video")
        return MagicMock(returncode=0)

    with patch("src.timelapse.subprocess.run") as mock_run:
        mock_run.side_effect = mock_ffmpeg_success
        build_timelapse(snapshots, output, fps=24, stabilize=True)

    assert mock_run.call_count == 2
    first_cmd = mock_run.call_args_list[0][0][0]
    second_cmd = mock_run.call_args_list[1][0][0]
    assert "vidstabdetect" in " ".join(first_cmd)
    assert "vidstabtransform" in " ".join(second_cmd)
    assert "mov_text" in second_cmd


def test_build_timelapse_stabilize_falls_back_on_pass1_failure(tmp_path):
    names = ["garden_2026-04-30_10-00-00_day.jpg"]
    snapshots = _make_snapshots(tmp_path, names)
    output = tmp_path / "timelapse_2026-04-30.mp4"

    call_count = 0

    def mock_ffmpeg(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(returncode=1, stderr="vidstab error")
        tmp_output = output.with_suffix(".tmp.mp4")
        tmp_output.write_bytes(b"fake video")
        return MagicMock(returncode=0)

    with patch("src.timelapse.subprocess.run") as mock_run:
        mock_run.side_effect = mock_ffmpeg
        build_timelapse(snapshots, output, fps=24, stabilize=True)

    assert output.exists()
