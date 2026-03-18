import logging
from typing import Optional
import time
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
# Scale candidates tried when the template doesn't fit at 1:1.
_SCALE_MIN = 0.6
_SCALE_MAX = 1.8
_SCALE_STEPS = 13
_SCALE_VALUES = np.linspace(_SCALE_MIN, _SCALE_MAX, _SCALE_STEPS)

# Confidence at which we stop trying further scales (early-exit).
_EARLY_EXIT_THRESHOLD = 0.95

# Minimum template size after scaling (pixels); avoids degenerate matches.
_MIN_TPL_DIM = 8

# ROI vertical crop used by shiki-detection helpers (fraction of frame height).
_ROI_TOP = 0.30
_ROI_BOTTOM = 0.85


class VisionMixin:
    # ── Internal helpers ───────────────────────────────────────────────────────

    def _load_template(self, image_name: str):
        """Return (frame, template) or (None, None) if either is unavailable."""
        frame = self._get_frame()
        if frame is None:
            return None, None
        tpl_path = self._images_dir / image_name
        if not tpl_path.exists():
            return None, None
        template = cv2.imread(str(tpl_path))
        if template is None:
            return None, None
        return frame, template

    @staticmethod
    def _match_template_scaled(
        haystack, needle, *, use_gray: bool, threshold: float
    ) -> tuple[float, Optional[tuple[int, int]], float]:
        """Try matching *needle* in *haystack* at scale 1.0 and then at scaled variants.

        Returns ``(best_val, best_loc, best_scale)`` where *best_loc* is the
        top-left corner of the best match (or ``None`` when nothing exceeded
        *threshold*).
        """
        if use_gray:
            haystack_g = cv2.cvtColor(haystack, cv2.COLOR_BGR2GRAY)
            needle_g = cv2.cvtColor(needle, cv2.COLOR_BGR2GRAY)
        else:
            haystack_g = haystack
            needle_g = needle

        fh, fw = haystack_g.shape[:2]
        th, tw = needle_g.shape[:2]

        # Try the native (1:1) scale first — cheapest path.
        if tw <= fw and th <= fh:
            result = cv2.matchTemplate(haystack_g, needle_g, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= _EARLY_EXIT_THRESHOLD:
                return max_val, max_loc, 1.0
            if max_val >= threshold:
                # Keep as best candidate but still try scales to see if we can do better.
                best_val, best_loc, best_scale = max_val, max_loc, 1.0
            else:
                best_val, best_loc, best_scale = -1.0, None, 1.0
        else:
            best_val, best_loc, best_scale = -1.0, None, 1.0

        # Try scaled variants.
        for scale in _SCALE_VALUES:
            if abs(scale - 1.0) < 0.05:
                continue
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w < _MIN_TPL_DIM or new_h < _MIN_TPL_DIM:
                continue
            if new_w > fw or new_h > fh:
                continue
            resized = cv2.resize(needle_g, (new_w, new_h), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(haystack_g, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_scale = scale
                if max_val >= _EARLY_EXIT_THRESHOLD:
                    break

        if best_val >= threshold and best_loc is not None:
            return best_val, best_loc, best_scale
        return best_val, None, best_scale

    # ── Public API ─────────────────────────────────────────────────────────────

    def _find_template(self, image_name: str, threshold: float = 0.8) -> Optional[tuple[int, int]]:
        frame, template = self._load_template(image_name)
        if frame is None:
            return None

        th, tw = template.shape[:2]
        _, best_loc, best_scale = self._match_template_scaled(
            frame, template, use_gray=True, threshold=threshold
        )
        if best_loc is None:
            return None
        cx = best_loc[0] + int(tw * best_scale) // 2
        cy = best_loc[1] + int(th * best_scale) // 2
        return (cx, cy)

    def _find_template_exact(self, image_name: str, threshold: float = 0.8) -> Optional[tuple[int, int]]:
        """Like _find_template but matches colour pixels (no grayscale conversion)."""
        frame, template = self._load_template(image_name)
        if frame is None:
            return None

        th, tw = template.shape[:2]
        _, best_loc, best_scale = self._match_template_scaled(
            frame, template, use_gray=False, threshold=threshold
        )
        if best_loc is None:
            return None
        cx = best_loc[0] + int(tw * best_scale) // 2
        cy = best_loc[1] + int(th * best_scale) // 2
        return (cx, cy)

    def _count_template(self, image_name: str, threshold: float = 0.8) -> int:
        frame, template = self._load_template(image_name)
        if frame is None:
            return 0

        fh, fw = frame.shape[:2]
        th, tw = template.shape[:2]
        if tw > fw or th > fh:
            return 0

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        locs = np.where(result >= threshold)
        points = list(zip(locs[1], locs[0]))

        if not points:
            return 0

        min_dist_x = max(1, tw // 2)
        min_dist_y = max(1, th // 2)
        kept = []
        for pt in points:
            for kpt in kept:
                if abs(pt[0] - kpt[0]) < min_dist_x and abs(pt[1] - kpt[1]) < min_dist_y:
                    break
            else:
                kept.append(pt)
        return len(kept)

    def _find_largest_shiki(self, dark_thresh: int = 50) -> Optional[tuple[int, int]]:
        frame = self._get_frame()
        if frame is None:
            return None

        h, w = frame.shape[:2]
        y1 = int(h * _ROI_TOP)
        y2 = int(h * _ROI_BOTTOM)
        roi = frame[y1:y2, :]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, dark_thresh, 255, cv2.THRESH_BINARY_INV)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
        if num_labels <= 1:
            return None

        areas = stats[1:, cv2.CC_STAT_AREA]
        best_label = int(np.argmax(areas)) + 1
        cx = int(centroids[best_label][0])
        cy = int(centroids[best_label][1]) + y1
        return (cx, cy)

    def _find_largest_moving(self, delay_ms: int = 33, motion_thresh: int = 25) -> Optional[tuple[int, int]]:
        frame = self._get_frame()
        if frame is None:
            return None

        h, w = frame.shape[:2]
        y1 = int(h * _ROI_TOP)
        y2 = int(h * _ROI_BOTTOM)
        roi = frame[y1:y2, :]

        small = cv2.resize(roi, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        prev = self._prev_gray_roi

        if prev is None or prev.shape != gray.shape:
            self._prev_gray_roi = gray
            time.sleep(delay_ms / 1000.0)
            frame2 = self._get_frame()
            if frame2 is None:
                return None
            roi2 = frame2[y1:y2, :]
            small2 = cv2.resize(roi2, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_NEAREST)
            gray2 = cv2.cvtColor(small2, cv2.COLOR_BGR2GRAY)
            self._prev_gray_roi = gray2
            diff = cv2.absdiff(gray, gray2)
        else:
            self._prev_gray_roi = gray
            diff = cv2.absdiff(prev, gray)

        _, bw = cv2.threshold(diff, motion_thresh, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        bw = cv2.dilate(bw, kernel, iterations=1)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
        if num_labels <= 1:
            return None

        areas = stats[1:, cv2.CC_STAT_AREA]
        best_label = int(np.argmax(areas)) + 1
        cx = int(centroids[best_label][0] * 2)
        cy = int(centroids[best_label][1] * 2) + y1
        return (cx, cy)
