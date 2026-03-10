from typing import Optional
import time
import numpy as np
import cv2

class VisionMixin:
    def _find_template(self, image_name: str, threshold: float = 0.8) -> Optional[tuple[int, int]]:
        frame = self._get_frame()
        if frame is None:
            return None
        tpl_path = self._images_dir / image_name
        if not tpl_path.exists():
            return None
        template = cv2.imread(str(tpl_path))
        if template is None:
            return None

        frame_h, frame_w = frame.shape[:2]
        tpl_h, tpl_w = template.shape[:2]

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        if tpl_w <= frame_w and tpl_h <= frame_h:
            result = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= threshold:
                cx = max_loc[0] + tpl_w // 2
                cy = max_loc[1] + tpl_h // 2
                return (cx, cy)

        best_val = -1.0
        best_loc = None
        best_scale = 1.0

        for scale in np.linspace(0.6, 1.8, 13):
            if abs(scale - 1.0) < 0.05:
                continue
            new_w = int(tpl_w * scale)
            new_h = int(tpl_h * scale)
            if new_w < 8 or new_h < 8:
                continue
            if new_w > frame_w or new_h > frame_h:
                continue
            resized_tpl = cv2.resize(tpl_gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(frame_gray, resized_tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_scale = scale
                if max_val >= 0.95:
                    break

        if best_val >= threshold and best_loc is not None:
            cx = best_loc[0] + int(tpl_w * best_scale) // 2
            cy = best_loc[1] + int(tpl_h * best_scale) // 2
            return (cx, cy)
        return None

    def _find_template_exact(self, image_name: str, threshold: float = 0.8) -> Optional[tuple[int, int]]:
        frame = self._get_frame()
        if frame is None:
            return None
        tpl_path = self._images_dir / image_name
        if not tpl_path.exists():
            return None
        template = cv2.imread(str(tpl_path))
        if template is None:
            return None

        frame_h, frame_w = frame.shape[:2]
        tpl_h, tpl_w = template.shape[:2]

        if tpl_w <= frame_w and tpl_h <= frame_h:
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= threshold:
                cx = max_loc[0] + tpl_w // 2
                cy = max_loc[1] + tpl_h // 2
                return (cx, cy)

        best_val = -1.0
        best_loc = None
        best_scale = 1.0

        for scale in np.linspace(0.6, 1.8, 13):
            if abs(scale - 1.0) < 0.05:
                continue
            new_w = int(tpl_w * scale)
            new_h = int(tpl_h * scale)
            if new_w < 8 or new_h < 8:
                continue
            if new_w > frame_w or new_h > frame_h:
                continue
            resized_tpl = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(frame, resized_tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_scale = scale
                if max_val >= 0.95:
                    break

        if best_val >= threshold and best_loc is not None:
            cx = best_loc[0] + int(tpl_w * best_scale) // 2
            cy = best_loc[1] + int(tpl_h * best_scale) // 2
            return (cx, cy)
        return None

    def _count_template(self, image_name: str, threshold: float = 0.8) -> int:
        frame = self._get_frame()
        if frame is None:
            return 0
        tpl_path = self._images_dir / image_name
        if not tpl_path.exists():
            return 0
        template = cv2.imread(str(tpl_path))
        if template is None:
            return 0

        frame_h, frame_w = frame.shape[:2]
        tpl_h, tpl_w = template.shape[:2]
        if tpl_w > frame_w or tpl_h > frame_h:
            return 0

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
        locs = np.where(result >= threshold)
        points = list(zip(locs[1], locs[0]))

        if not points:
            return 0

        min_dist_x = max(1, tpl_w // 2)
        min_dist_y = max(1, tpl_h // 2)
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
        y1 = int(h * 0.30)
        y2 = int(h * 0.85)
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
        y1 = int(h * 0.30)
        y2 = int(h * 0.85)
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
