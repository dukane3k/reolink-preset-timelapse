from __future__ import annotations
import logging
import tempfile
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

_MIN_MATCH_COUNT = 10


def _load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _align_to_reference(
    reference_gray: np.ndarray,
    reference_img: np.ndarray,
    target_path: Path,
) -> np.ndarray | None:
    """Return target image warped to align with reference, or None on failure."""
    target_img = cv2.imread(str(target_path))
    if target_img is None:
        log.warning("Could not read %s, skipping alignment", target_path)
        return None
    target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)

    detector = cv2.ORB_create(nfeatures=2000)
    kp_ref, desc_ref = detector.detectAndCompute(reference_gray, None)
    kp_tgt, desc_tgt = detector.detectAndCompute(target_gray, None)

    if desc_ref is None or desc_tgt is None or len(kp_ref) < _MIN_MATCH_COUNT or len(kp_tgt) < _MIN_MATCH_COUNT:
        log.warning("Not enough features in %s, using unaligned", target_path.name)
        return target_img

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = matcher.knnMatch(desc_ref, desc_tgt, k=2)

    # Lowe's ratio test
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]

    if len(good) < _MIN_MATCH_COUNT:
        log.warning("Too few good matches (%d) for %s, using unaligned", len(good), target_path.name)
        return target_img

    src_pts = np.float32([kp_ref[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_tgt[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None:
        log.warning("Homography failed for %s, using unaligned", target_path.name)
        return target_img

    h, w = reference_img.shape[:2]
    aligned = cv2.warpPerspective(target_img, H, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return aligned


def _compute_crop(snapshots: list[Path], reference_img: np.ndarray, reference_gray: np.ndarray) -> tuple[int, int, int, int]:
    """
    Compute the largest central crop region that is fully covered across all aligned frames.
    Returns (x, y, w, h) in pixels.
    """
    h, w = reference_img.shape[:2]
    # Start with full frame, shrink to covered region
    x0, y0, x1, y1 = 0, 0, w, h

    for snap in snapshots[1:]:
        aligned = _align_to_reference(reference_gray, reference_img, snap)
        if aligned is None:
            continue
        # Find rows/cols that are fully non-black (any channel > 0)
        mask = np.any(aligned > 0, axis=2).astype(np.uint8)
        cols = np.where(mask.any(axis=0))[0]
        rows = np.where(mask.any(axis=1))[0]
        if len(cols) == 0 or len(rows) == 0:
            continue
        x0 = max(x0, int(cols[0]))
        x1 = min(x1, int(cols[-1]) + 1)
        y0 = max(y0, int(rows[0]))
        y1 = min(y1, int(rows[-1]) + 1)

    # Ensure even dimensions for libx264
    cw = ((x1 - x0) // 2) * 2
    ch = ((y1 - y0) // 2) * 2
    return x0, y0, cw, ch


def align_snapshots(snapshots: list[Path], output_dir: Path) -> list[Path]:
    """
    Align all snapshots to the first frame using feature matching.
    Writes aligned JPEGs to output_dir and returns their paths in order.
    Automatically crops to the largest region covered by all frames.
    """
    if not snapshots:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    reference_img = cv2.imread(str(snapshots[0]))
    if reference_img is None:
        log.error("Could not read reference frame %s", snapshots[0])
        return snapshots
    reference_gray = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)

    log.info("Computing alignment crop region across %d frames...", len(snapshots))
    x, y, cw, ch = _compute_crop(snapshots, reference_img, reference_gray)
    log.info("Crop region: x=%d y=%d w=%d h=%d", x, y, cw, ch)

    aligned_paths: list[Path] = []

    # Write reference frame (cropped)
    ref_out = output_dir / snapshots[0].name
    cv2.imwrite(str(ref_out), reference_img[y:y+ch, x:x+cw])
    aligned_paths.append(ref_out)

    for snap in snapshots[1:]:
        aligned = _align_to_reference(reference_gray, reference_img, snap)
        if aligned is None:
            aligned = cv2.imread(str(snap)) or reference_img
        cropped = aligned[y:y+ch, x:x+cw]
        out_path = output_dir / snap.name
        cv2.imwrite(str(out_path), cropped)
        aligned_paths.append(out_path)

    log.info("Aligned %d frames", len(aligned_paths))
    return aligned_paths
