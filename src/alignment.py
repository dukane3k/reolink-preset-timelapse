from __future__ import annotations
import logging
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

# ECC convergence criteria: max 50 iterations, epsilon 1e-4
_ECC_CRITERIA = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-4)


def _align_to_reference(
    reference_gray: np.ndarray,
    reference_img: np.ndarray,
    target_path: Path,
) -> np.ndarray:
    """Return target image translated to align with reference using ECC. Falls back to unaligned on failure."""
    target_img = cv2.imread(str(target_path))
    if target_img is None:
        log.warning("Could not read %s, using reference frame", target_path)
        return reference_img.copy()
    target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)

    # Translation-only warp: 2x3 identity matrix as starting point
    warp_matrix = np.eye(2, 3, dtype=np.float32)

    try:
        _, warp_matrix = cv2.findTransformECC(
            reference_gray,
            target_gray,
            warp_matrix,
            cv2.MOTION_TRANSLATION,
            _ECC_CRITERIA,
        )
    except cv2.error as e:
        log.warning("ECC failed for %s (%s), using unaligned", target_path.name, e)
        return target_img

    h, w = reference_img.shape[:2]
    aligned = cv2.warpAffine(
        target_img,
        warp_matrix,
        (w, h),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    dx = abs(warp_matrix[0, 2])
    dy = abs(warp_matrix[1, 2])
    log.debug("ECC shift for %s: dx=%.1f dy=%.1f", target_path.name, dx, dy)

    return aligned


def _edge_crop(img: np.ndarray, percent: int) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) cropping percent% from each edge."""
    h, w = img.shape[:2]
    px = int(w * percent / 100)
    py = int(h * percent / 100)
    cw = ((w - px * 2) // 2) * 2
    ch = ((h - py * 2) // 2) * 2
    return px, py, cw, ch


def align_snapshots(snapshots: list[Path], output_dir: Path, crop_percent: int = 5) -> list[Path]:
    """
    Align all snapshots to the first frame using ECC translation estimation.
    Crops crop_percent% from each edge to remove warp border artifacts.
    Writes aligned JPEGs to output_dir and returns their paths in order.
    """
    if not snapshots:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    reference_img = cv2.imread(str(snapshots[0]))
    if reference_img is None:
        log.error("Could not read reference frame %s, skipping alignment", snapshots[0])
        return snapshots
    reference_gray = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)

    x, y, cw, ch = _edge_crop(reference_img, crop_percent)
    log.info("Aligning %d frames, crop=%d%% → %dx%d", len(snapshots), crop_percent, cw, ch)

    aligned_paths: list[Path] = []

    ref_out = output_dir / snapshots[0].name
    cv2.imwrite(str(ref_out), reference_img[y:y+ch, x:x+cw])
    aligned_paths.append(ref_out)

    for snap in snapshots[1:]:
        aligned = _align_to_reference(reference_gray, reference_img, snap)
        out_path = output_dir / snap.name
        cv2.imwrite(str(out_path), aligned[y:y+ch, x:x+cw])
        aligned_paths.append(out_path)

    log.info("Aligned %d frames", len(aligned_paths))
    return aligned_paths
