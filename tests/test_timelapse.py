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
