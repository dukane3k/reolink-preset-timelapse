import pytest
import numpy as np
import cv2
from pathlib import Path
from src.alignment import align_snapshots


def _write_jpg(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def _solid(color: tuple, size: tuple = (480, 640, 3)) -> np.ndarray:
    img = np.zeros(size, dtype=np.uint8)
    img[:] = color
    return img


def _checkerboard(size: tuple = (480, 640, 3), tile: int = 40) -> np.ndarray:
    img = np.zeros(size, dtype=np.uint8)
    for y in range(0, size[0], tile):
        for x in range(0, size[1], tile):
            if (x // tile + y // tile) % 2 == 0:
                img[y:y+tile, x:x+tile] = (200, 200, 200)
    return img


def test_align_snapshots_returns_same_count(tmp_path):
    snap_dir = tmp_path / "snaps"
    out_dir = tmp_path / "aligned"
    names = [
        "garden_2026-04-30_10-00-00_day.jpg",
        "garden_2026-04-30_10-30-00_day.jpg",
        "garden_2026-04-30_11-00-00_day.jpg",
    ]
    snaps = []
    for name in names:
        p = snap_dir / name
        _write_jpg(p, _checkerboard())
        snaps.append(p)

    result = align_snapshots(snaps, out_dir)
    assert len(result) == len(snaps)


def test_align_snapshots_output_files_exist(tmp_path):
    snap_dir = tmp_path / "snaps"
    out_dir = tmp_path / "aligned"
    p = snap_dir / "garden_2026-04-30_10-00-00_day.jpg"
    _write_jpg(p, _checkerboard())

    result = align_snapshots([p], out_dir)
    assert result[0].exists()


def test_align_snapshots_empty_returns_empty(tmp_path):
    result = align_snapshots([], tmp_path / "aligned")
    assert result == []


def test_align_snapshots_output_has_even_dimensions(tmp_path):
    snap_dir = tmp_path / "snaps"
    out_dir = tmp_path / "aligned"
    names = [
        "garden_2026-04-30_10-00-00_day.jpg",
        "garden_2026-04-30_10-30-00_day.jpg",
    ]
    snaps = []
    for name in names:
        p = snap_dir / name
        _write_jpg(p, _checkerboard())
        snaps.append(p)

    result = align_snapshots(snaps, out_dir)
    for r in result:
        img = cv2.imread(str(r))
        h, w = img.shape[:2]
        assert w % 2 == 0
        assert h % 2 == 0
