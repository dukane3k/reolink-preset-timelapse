from __future__ import annotations
import logging
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

_MIN_MATCH_COUNT = 10


def _align_to_reference(
    reference_gray: np.ndarray,
    reference_img: np.ndarray,
    target_path: Path,
) -> np.ndarray:
    """Return target image warped to align with reference. Falls back to unaligned on failure."""
    target_img = cv2.imread(str(target_path))
    if target_img is None:
        log.warning("Could not read %s, using reference frame", target_path)
        return reference_img.copy()
    target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)

    detector = cv2.ORB_create(nfeatures=2000)
    kp_ref, desc_ref = detector.detectAndCompute(reference_gray, None)
    kp_tgt, desc_tgt = detector.detectAndCompute(target_gray, None)

    if desc_ref is None or desc_tgt is None or len(kp_ref) < _MIN_MATCH_COUNT or len(kp_tgt) < _MIN_MATCH_COUNT:
        log.warning("Not enough features in %s, using unaligned", target_path.name)
        return target_img

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = matcher.knnMatch(desc_ref, desc_tgt, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]

    if len(good) < _MIN_MATCH_COUNT:
        log.warning("Too few good matches (%d) for %s, using unaligned", len(good), target_path.name)
        return target_img

    src_pts = np.float32([kp_ref[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_tgt[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    H, _ = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None:
        log.warning("Homography failed for %s, using unaligned", target_path.name)
        return target_img

    h, w = reference_img.shape[:2]
    return cv2.warpPerspective(target_img, H, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


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
    Align all snapshots to the first frame using ORB feature matching + homography.
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
