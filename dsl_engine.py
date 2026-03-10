"""
DSL Engine – bộ thông dịch script đơn giản cho game bot.

Cú pháp:
    click X Y
    rclick X Y
    dclick X Y
    move X Y
    drag X1 Y1 X2 Y2
    drag_to 'img1.png' 'img2.png' [THRESHOLD]  # drag từ vị trí ảnh 1 đến ảnh 2
    drag_offset 'img.png' DX DY             # tìm ảnh, kéo từ tâm ảnh đến tâm ảnh cộng offset (DX, DY)
    key KEYNAME
    type "text"
    wait SECONDS
    wait_random MIN MAX
    log "message"
    find_and_click 'image.png' [THRESHOLD]
    wait_for 'image.png' TIMEOUT
    wait_and_click 'image.png' TIMEOUT
    exists 'image.png'              (dùng trong if)
    loop N / loop forever ... end
    if exists 'img' ... elif ... else ... end
    set VAR VALUE / set VAR + N / set VAR - N
    resize W H                       (resize cửa sổ game, vd: resize 1920 1080)
    do ... until <condition>          (lặp cho đến khi condition đúng)
    label_name:                       (nhãn – dòng kết thúc bằng :)
    goto label_name                   (nhảy đến nhãn)
    count VAR 'image.png' [THRESHOLD] (dếm số lần ảnh xuất hiện, lưu vào biến VAR)
    find_and_click_largest_shiki [DARK_THRESH]  (tìm & click silhouette đen lớn nhất, mặc định thresh=50)
    throw_at_largest_shiki [DELAY_MS] [MOTION_THRESH]  (click vật thể chuyển động lớn nhất)
"""

import re
import time
import random
import threading
import ctypes
import ctypes.wintypes
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
import win32api
import win32con
import win32gui

from screenshot import WindowCapture


class DSLError(Exception):
    pass


class DSLEngine:
    """Thông dịch và chạy DSL script."""

    def __init__(self):
        self._capture: Optional[WindowCapture] = None
        self._last_frame: Optional[np.ndarray] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._variables: dict[str, float] = {}
        self._images_dir = Path("images")
        self._reference_size: tuple[int, int] = (1920, 1080)  # kích thước chuẩn cho template
        self._prev_gray_roi: Optional[np.ndarray] = None  # cached for motion detection

    # -- External setters ---------------------------------------------------

    def set_capture(self, capture: Optional[WindowCapture]):
        with self._lock:
            self._capture = capture

    def set_last_frame(self, frame: np.ndarray):
        with self._lock:
            self._last_frame = frame.copy()

    def request_stop(self):
        self._stop_event.set()

    def reset_stop(self):
        self._stop_event.clear()

    # -- Helpers ------------------------------------------------------------

    def _get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._last_frame is not None:
                return self._last_frame.copy()
        # fallback: capture trực tiếp
        with self._lock:
            cap = self._capture
        if cap:
            return cap.capture()
        return None

    def _window_click(self, x: int, y: int, button="left", double=False):
        """Click tại tọa độ (x, y) trong cửa sổ game (client coords)."""
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        # Chuyển từ client coords sang screen coords
        screen_x, screen_y = win32gui.ClientToScreen(cap.hwnd, (x, y))
        lparam = win32api.MAKELONG(x, y)
        if button == "left":
            win32gui.PostMessage(cap.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(0.05)
            win32gui.PostMessage(cap.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            if double:
                time.sleep(0.05)
                win32gui.PostMessage(cap.hwnd, win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, lparam)
                time.sleep(0.05)
                win32gui.PostMessage(cap.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        elif button == "right":
            win32gui.PostMessage(cap.hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lparam)
            time.sleep(0.05)
            win32gui.PostMessage(cap.hwnd, win32con.WM_RBUTTONUP, 0, lparam)

    def _window_move(self, x: int, y: int):
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        lparam = win32api.MAKELONG(x, y)
        win32gui.PostMessage(cap.hwnd, win32con.WM_MOUSEMOVE, 0, lparam)

    def _window_drag(self, x1, y1, x2, y2, steps=20):
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        for i in range(steps + 1):
            t = i / steps
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)
            lparam = win32api.MAKELONG(cx, cy)
            if i == 0:
                win32gui.PostMessage(cap.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            else:
                win32gui.PostMessage(cap.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lparam)
            time.sleep(0.01)
        lparam = win32api.MAKELONG(x2, y2)
        win32gui.PostMessage(cap.hwnd, win32con.WM_LBUTTONUP, 0, lparam)

    def _window_scroll(self, delta: int):
        """Scroll vertical wheel by the given delta ticks (positive = up)."""
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        # Use current cursor position inside window for lparam
        try:
            x, y = win32gui.GetCursorPos()
            x, y = win32gui.ScreenToClient(cap.hwnd, (x, y))
        except Exception:
            x, y = (0, 0)
        lparam = win32api.MAKELONG(x, y)
        wparam = delta * win32con.WHEEL_DELTA
        win32gui.PostMessage(cap.hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)

    def _window_key(self, key_name: str):
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        vk = _key_name_to_vk(key_name)
        if vk is None:
            return
        win32gui.PostMessage(cap.hwnd, win32con.WM_KEYDOWN, vk, 0)
        time.sleep(0.05)
        win32gui.PostMessage(cap.hwnd, win32con.WM_KEYUP, vk, 0)

    def _window_type_text(self, text: str):
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        for ch in text:
            win32gui.PostMessage(cap.hwnd, win32con.WM_CHAR, ord(ch), 0)
            time.sleep(0.02)

    def resize_window(self, width: int = 1920, height: int = 1080):
        """Resize cửa sổ game về kích thước client area mong muốn."""
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        hwnd = cap.hwnd
        # Tính kích thước window thực tế (bao gồm title bar, border)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        has_menu = win32gui.GetMenu(hwnd) != 0
        rect = ctypes.wintypes.RECT(0, 0, width, height)
        ctypes.windll.user32.AdjustWindowRectEx(
            ctypes.byref(rect), style, has_menu, ex_style
        )
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        # Lấy vị trí hiện tại
        cur_rect = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(hwnd, cur_rect[0], cur_rect[1], win_w, win_h, True)

    def _find_template(self, image_name: str, threshold: float = 0.8) -> Optional[tuple[int, int]]:
        """Multi-scale template matching. Trả về (cx, cy) tọa độ thật của cửa sổ.
        Đây là hàm đã tồn tại, dùng cho các lệnh cần tâm ảnh (click, drag to, ...).
        """
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

        # Chuyển sang grayscale để match nhanh hơn
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        # 1) Thử exact scale trước (nhanh nhất, ít false positive)
        if tpl_w <= frame_w and tpl_h <= frame_h:
            result = cv2.matchTemplate(frame_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= threshold:
                cx = max_loc[0] + tpl_w // 2
                cy = max_loc[1] + tpl_h // 2
                return (cx, cy)

        # 2) Multi-scale: chỉ khi exact không match, thử các tỷ lệ gần
        best_val = -1.0
        best_loc = None
        best_scale = 1.0

        for scale in np.linspace(0.6, 1.8, 13):
            if abs(scale - 1.0) < 0.05:
                continue  # đã thử exact rồi
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
                # Early exit nếu confidence rất cao
                if max_val >= 0.95:
                    break

        if best_val >= threshold and best_loc is not None:
            cx = best_loc[0] + int(tpl_w * best_scale) // 2
            cy = best_loc[1] + int(tpl_h * best_scale) // 2
            return (cx, cy)
        return None

    def _find_template_exact(self, image_name: str, threshold: float = 0.8) -> Optional[tuple[int, int]]:
        """Template matching trên ảnh màu (BGR), không grayscale. Chính xác hơn về màu sắc."""
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

        # Exact scale trên ảnh màu
        if tpl_w <= frame_w and tpl_h <= frame_h:
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= threshold:
                cx = max_loc[0] + tpl_w // 2
                cy = max_loc[1] + tpl_h // 2
                return (cx, cy)

        # Multi-scale trên ảnh màu
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
        """Dếm tất cả vị trí xuất hiện của template trên frame (grayscale, exact scale)."""
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
        # Lấy tất cả vị trí vượt threshold, dùng non-max suppression theo khoảng cách
        locs = np.where(result >= threshold)
        points = list(zip(locs[1], locs[0]))  # (x, y)

        if not points:
            return 0

        # NMS: loại bỏ các điểm quá gần nhau (< 50% kích thước template)
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
        """Detect the largest dark silhouette (shikigami) and return its center.

        Optimised for speed:
        - works on a single grayscale threshold (no template matching)
        - crops to the middle band of the screen where shikigami appear
        - uses cv2.connectedComponentsWithStats (faster than findContours
          for area queries)
        """
        frame = self._get_frame()
        if frame is None:
            return None

        h, w = frame.shape[:2]

        # ROI: vertical 30%-85%, horizontal full width
        y1 = int(h * 0.30)
        y2 = int(h * 0.85)
        roi = frame[y1:y2, :]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # dark pixels -> white
        _, bw = cv2.threshold(gray, dark_thresh, 255, cv2.THRESH_BINARY_INV)

        # connected components with stats (label 0 = background)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
        if num_labels <= 1:
            return None

        # find component with largest area (skip label 0 = bg)
        areas = stats[1:, cv2.CC_STAT_AREA]
        best_label = int(np.argmax(areas)) + 1  # +1 because we skipped label 0
        cx = int(centroids[best_label][0])
        cy = int(centroids[best_label][1]) + y1  # translate back to full-frame coords
        return (cx, cy)

    def _find_largest_moving(self, delay_ms: int = 33, motion_thresh: int = 25) -> Optional[tuple[int, int]]:
        """Detect the largest moving object by frame differencing.

        Uses a cached previous grayscale ROI so the first call stores the
        frame and the second call (typically next loop iteration) can diff
        instantly without any sleep.  Falls back to a short sleep only when
        there is no cached frame.

        Processing is done on a 0.5× downscaled image for speed; the
        returned coordinates are mapped back to full resolution.
        """
        frame = self._get_frame()
        if frame is None:
            return None

        h, w = frame.shape[:2]
        y1 = int(h * 0.30)
        y2 = int(h * 0.85)
        roi = frame[y1:y2, :]

        # downscale 0.5× for speed
        small = cv2.resize(roi, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        prev = self._prev_gray_roi

        if prev is None or prev.shape != gray.shape:
            # no cached frame yet — store and do a quick re-capture
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
            # instant diff against cached frame
            self._prev_gray_roi = gray
            diff = cv2.absdiff(prev, gray)

        _, bw = cv2.threshold(diff, motion_thresh, 255, cv2.THRESH_BINARY)

        # single dilate pass on small image
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        bw = cv2.dilate(bw, kernel, iterations=1)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
        if num_labels <= 1:
            return None

        areas = stats[1:, cv2.CC_STAT_AREA]
        best_label = int(np.argmax(areas)) + 1
        # scale centroid back to full resolution
        cx = int(centroids[best_label][0] * 2)
        cy = int(centroids[best_label][1] * 2) + y1
        return (cx, cy)

    # -- Parser / tokenizer -------------------------------------------------

    @staticmethod
    def _parse_lines(script: str) -> list[str]:
        lines = []
        for raw in script.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
        return lines

    @staticmethod
    def _parse_string_arg(token: str) -> str:
        """Strip quotes: 'abc' or \"abc\" -> abc"""
        if (token.startswith("'") and token.endswith("'")) or \
           (token.startswith('"') and token.endswith('"')):
            return token[1:-1]
        return token

    # -- Execute ------------------------------------------------------------

    def execute(self, script: str, log_fn: Optional[Callable[[str], None]] = None):
        """Chạy DSL script (blocking). Gọi từ worker thread."""
        self._variables.clear()
        self._prev_gray_roi = None  # reset motion detection cache
        lines = self._parse_lines(script)
        # Build label map: label_name -> line index
        self._labels: dict[str, int] = {}
        for idx, ln in enumerate(lines):
            stripped = ln.strip()
            if stripped.endswith(":") and not stripped.startswith("#"):
                label_name = stripped[:-1].strip()
                self._labels[label_name] = idx
        self._exec_block(lines, 0, len(lines), log_fn)

    def _exec_block(self, lines: list[str], start: int, end: int,
                    log_fn: Optional[Callable[[str], None]]) -> int:
        i = start
        while i < end:
            if self._stop_event.is_set():
                return end
            line = lines[i]
            tokens = _tokenize(line)
            cmd = tokens[0].lower()

            if cmd == "click":
                x, y = int(tokens[1]), int(tokens[2])
                self._window_click(x, y)
                if log_fn:
                    log_fn(f"click {x} {y}")
            elif cmd == "rclick":
                x, y = int(tokens[1]), int(tokens[2])
                self._window_click(x, y, button="right")
            elif cmd == "dclick":
                x, y = int(tokens[1]), int(tokens[2])
                self._window_click(x, y, double=True)
            elif cmd == "move":
                x, y = int(tokens[1]), int(tokens[2])
                self._window_move(x, y)
            elif cmd == "drag":
                self._window_drag(int(tokens[1]), int(tokens[2]),
                                  int(tokens[3]), int(tokens[4]))
            elif cmd in ("drag_to", "drag_image"):
                # drag from image1 to image2; optional threshold applies to both
                img1 = self._parse_string_arg(tokens[1])
                img2 = self._parse_string_arg(tokens[2])
                thresh = float(tokens[3]) if len(tokens) > 3 else 0.8
                pos1 = self._find_template(img1, thresh)
                pos2 = self._find_template(img2, thresh) if pos1 else None
                if pos1 and pos2:
                    self._window_drag(pos1[0], pos1[1], pos2[0], pos2[1])
                    if log_fn:
                        log_fn(f"drag {img1}@{pos1} -> {img2}@{pos2}")
                else:
                    if log_fn:
                        log_fn(f"drag_to failed: {img1} or {img2} not found")
            elif cmd == "drag_offset":
                # drag_offset 'image' DX DY
                img = self._parse_string_arg(tokens[1])
                dx = int(tokens[2])
                dy = int(tokens[3])
                pos = self._find_template(img)
                if pos is not None:
                    start_x, start_y = pos
                    end_x = start_x + dx
                    end_y = start_y + dy
                    self._window_drag(start_x, start_y, end_x, end_y)
                    if log_fn:
                        log_fn(f"drag_offset {img} center+({dx},{dy})")
                else:
                    if log_fn:
                        log_fn(f"drag_offset failed: image not found")
            elif cmd == "scroll":
                # scroll N
                amount = int(tokens[1])
                self._window_scroll(amount)
                if log_fn:
                    log_fn(f"scroll {amount}")
            elif cmd == "key":
                self._window_key(tokens[1])
            elif cmd == "type":
                text = self._parse_string_arg(tokens[1])
                self._window_type_text(text)
            elif cmd == "count":
                var = tokens[1]
                img = self._parse_string_arg(tokens[2])
                thresh = float(tokens[3]) if len(tokens) > 3 else 0.8
                n = self._count_template(img, thresh)
                self._variables[var] = float(n)
                if log_fn:
                    log_fn(f"count {img} = {n}")
            elif cmd == "wait":
                secs = self._resolve_value(tokens[1])
                self._interruptible_sleep(secs)
            elif cmd == "wait_random":
                lo = float(tokens[1])
                hi = float(tokens[2])
                self._interruptible_sleep(random.uniform(lo, hi))
            elif cmd == "log":
                msg = self._parse_string_arg(tokens[1]) if len(tokens) > 1 else ""
                if log_fn:
                    log_fn(msg)
            elif cmd == "find_and_click_largest_shiki":
                thresh_val = int(tokens[1]) if len(tokens) > 1 else 50
                pos = self._find_largest_shiki(dark_thresh=thresh_val)
                if pos:
                    self._window_click(pos[0], pos[1])
                    if log_fn:
                        log_fn(f"clicked largest shiki at {pos}")
                else:
                    if log_fn:
                        log_fn("no shiki silhouette found")
            elif cmd == "throw_at_largest_shiki":
                delay = int(tokens[1]) if len(tokens) > 1 else 100
                mt = int(tokens[2]) if len(tokens) > 2 else 30
                pos = self._find_largest_moving(delay_ms=delay, motion_thresh=mt)
                if pos:
                    self._window_click(pos[0], pos[1])
                    if log_fn:
                        log_fn(f"threw at moving shiki at {pos}")
                else:
                    if log_fn:
                        log_fn("no moving shiki detected")
            elif cmd == "find_and_click":
                images, thresh = self._parse_find_args(tokens[1:])
                for img in images:
                    pos = self._find_template(img, thresh)
                    if pos:
                        self._window_click(pos[0], pos[1])
                        if log_fn:
                            log_fn(f"found & clicked {img} at {pos}")
                        break
                else:
                    if log_fn:
                        names = ", ".join(images)
                        log_fn(f"not found: [{names}]")
            elif cmd == "wait_for":
                images, timeout = self._parse_wait_args(tokens[1:])
                self._wait_for_images(images, timeout, log_fn)
            elif cmd == "wait_and_click":
                images, timeout = self._parse_wait_args(tokens[1:])
                result = self._wait_for_images(images, timeout, log_fn)
                if result:
                    self._window_click(result[1][0], result[1][1])
            elif cmd == "resize":
                rw = int(tokens[1]) if len(tokens) > 1 else 1920
                rh = int(tokens[2]) if len(tokens) > 2 else 1080
                self.resize_window(rw, rh)
                if log_fn:
                    log_fn(f"resize window to {rw}x{rh}")
            elif cmd == "set":
                self._handle_set(tokens)
            elif cmd == "do":
                block_end = _find_matching_until(lines, i)
                until_tokens = _tokenize(lines[block_end])
                # until_tokens: ['until', ...condition tokens...]
                condition_tokens = until_tokens[1:]
                while not self._stop_event.is_set():
                    self._exec_block(lines, i + 1, block_end, log_fn)
                    if self._eval_condition(condition_tokens):
                        break
                i = block_end + 1
                continue
            elif cmd == "until":
                # reached by block executor – just skip
                pass
            elif cmd == "loop":
                block_end = _find_matching_end(lines, i)
                count_token = tokens[1].lower() if len(tokens) > 1 else "forever"
                if count_token == "forever":
                    while not self._stop_event.is_set():
                        self._exec_block(lines, i + 1, block_end, log_fn)
                else:
                    n = int(self._resolve_value(count_token))
                    for _ in range(n):
                        if self._stop_event.is_set():
                            break
                        self._exec_block(lines, i + 1, block_end, log_fn)
                i = block_end + 1
                continue
            elif cmd == "if":
                i = self._handle_if(lines, i, end, log_fn)
                continue
            elif cmd in ("end", "else", "elif", "until"):
                # reached by block executor – just skip
                pass
            elif cmd == "goto":
                label = tokens[1] if len(tokens) > 1 else ""
                if label in self._labels:
                    if log_fn:
                        log_fn(f"goto {label}")
                    i = self._labels[label]
                    continue
                else:
                    if log_fn:
                        log_fn(f"Label not found: {label}")
            elif line.endswith(":"):
                # label definition – skip
                pass
            else:
                if log_fn:
                    log_fn(f"Unknown command: {line}")
            i += 1
        return i

    def _handle_set(self, tokens: list[str]):
        var = tokens[1]
        if len(tokens) == 3:
            self._variables[var] = float(tokens[2])
        elif len(tokens) == 4:
            op = tokens[2]
            val = float(tokens[3])
            cur = self._variables.get(var, 0)
            if op == "+":
                self._variables[var] = cur + val
            elif op == "-":
                self._variables[var] = cur - val
            elif op == "*":
                self._variables[var] = cur * val
            elif op == "/":
                self._variables[var] = cur / val if val != 0 else cur

    def _handle_if(self, lines: list[str], start: int, block_end: int,
                   log_fn) -> int:
        """Xử lý if/elif/else/end. Trả về index sau end."""
        # Tìm tất cả branches
        branches: list[tuple[str, int, int]] = []  # (condition_line, body_start, body_end)
        i = start
        depth = 0
        branch_starts: list[int] = [start]

        for j in range(start, block_end):
            tok0 = _tokenize(lines[j])[0].lower()
            if tok0 in ("loop", "if"):
                if j != start:
                    depth += 1
            elif tok0 == "end":
                if depth == 0:
                    branch_starts.append(j)
                    break
                depth -= 1
            elif tok0 in ("elif", "else") and depth == 0:
                branch_starts.append(j)

        # Build branches
        for idx in range(len(branch_starts) - 1):
            cond_line = lines[branch_starts[idx]]
            body_start = branch_starts[idx] + 1
            body_end = branch_starts[idx + 1]
            branches.append((cond_line, body_start, body_end))

        end_idx = branch_starts[-1]

        for cond_line, bstart, bend in branches:
            toks = _tokenize(cond_line)
            cmd = toks[0].lower()
            if cmd == "else":
                self._exec_block(lines, bstart, bend, log_fn)
                break
            # if / elif  – evaluate condition
            if self._eval_condition(toks[1:]):
                self._exec_block(lines, bstart, bend, log_fn)
                break

        return end_idx + 1

    def _eval_condition(self, tokens: list[str]) -> bool:
        # support simple logical operators AND/OR between sub-conditions and unary NOT
        if not tokens:
            return False
        # handle unary not at beginning
        if tokens[0].lower() == "not":
            return not self._eval_condition(tokens[1:])
        # look for top-level and/or (left-to-right, no precedence grouping)
        if "and" in tokens:
            idx = tokens.index("and")
            return self._eval_condition(tokens[:idx]) and self._eval_condition(tokens[idx+1:])
        if "or" in tokens:
            idx = tokens.index("or")
            return self._eval_condition(tokens[:idx]) or self._eval_condition(tokens[idx+1:])

        # single token may be a boolean variable name
        if len(tokens) == 1:
            return bool(self._variables.get(tokens[0], 0))

        cmd = tokens[0].lower()
        if cmd == "exists":
            img = self._parse_string_arg(tokens[1])
            thresh = float(tokens[2]) if len(tokens) > 2 else 0.8
            return self._find_template(img, thresh) is not None
        if cmd == "exists_exact":
            img = self._parse_string_arg(tokens[1])
            thresh = float(tokens[2]) if len(tokens) > 2 else 0.8
            return self._find_template_exact(img, thresh) is not None
        # variable comparison: var > N, var < N, var == N
        if len(tokens) >= 3:
            var_val = self._variables.get(tokens[0], 0)
            op = tokens[1]
            rhs_tok = tokens[2]
            # interpret boolean rhs
            if rhs_tok.lower() in ("true", "false"):
                rhs = 1.0 if rhs_tok.lower() == "true" else 0.0
            else:
                try:
                    rhs = float(rhs_tok)
                except ValueError:
                    rhs = self._variables.get(rhs_tok, 0)
            if op == ">":
                return var_val > rhs
            elif op == "<":
                return var_val < rhs
            elif op in ("==", "="):
                return var_val == rhs
            elif op == ">=":
                return var_val >= rhs
            elif op == "<=":
                return var_val <= rhs
            elif op == "!=":
                return var_val != rhs
        return False

    @staticmethod
    def _parse_find_args(tokens: list[str]) -> tuple[list[str], float]:
        """Parse danh sách ảnh và threshold từ tokens. Trả về (images, threshold)."""
        images = []
        threshold = 0.8
        for t in tokens:
            if (t.startswith("'") and t.endswith("'")) or \
               (t.startswith('"') and t.endswith('"')):
                images.append(t[1:-1])
            else:
                try:
                    threshold = float(t)
                except ValueError:
                    images.append(t)
        return images, threshold

    @staticmethod
    def _parse_wait_args(tokens: list[str]) -> tuple[list[str], float]:
        """Parse danh sách ảnh và timeout từ tokens. Trả về (images, timeout)."""
        images = []
        timeout = 0.0
        for t in tokens:
            # Nếu là quoted string -> ảnh
            if (t.startswith("'") and t.endswith("'")) or \
               (t.startswith('"') and t.endswith('"')):
                images.append(t[1:-1])
            else:
                # Thử parse số -> timeout
                try:
                    timeout = float(t)
                except ValueError:
                    # Không phải số, coi như tên ảnh không quote
                    images.append(t)
        return images, timeout

    def _wait_for_images(self, image_names: list[str], timeout: float,
                         log_fn) -> Optional[tuple[str, tuple[int, int]]]:
        """Chờ bất kỳ ảnh nào xuất hiện. Trả về (image_name, (cx, cy)) hoặc None."""
        start = time.time()
        names_str = ", ".join(image_names)
        if timeout > 0:
            if log_fn:
                log_fn(f"Waiting for [{names_str}] (timeout {timeout}s)...")
        else:
            if log_fn:
                log_fn(f"Waiting for [{names_str}] (no timeout)...")
        while True:
            if self._stop_event.is_set():
                return None
            if timeout > 0 and time.time() - start >= timeout:
                if log_fn:
                    log_fn(f"Timeout waiting for [{names_str}]")
                return None
            for img in image_names:
                pos = self._find_template(img)
                if pos:
                    if log_fn:
                        log_fn(f"Found {img} at {pos}")
                    return (img, pos)
            time.sleep(0.5)

    def _wait_for_image(self, image_name: str, timeout: float,
                        log_fn) -> Optional[tuple[int, int]]:
        """Chờ 1 ảnh xuất hiện. Wrapper cho _wait_for_images."""
        result = self._wait_for_images([image_name], timeout, log_fn)
        if result:
            return result[1]
        return None

    def _interruptible_sleep(self, seconds: float):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self._stop_event.is_set():
                return
            time.sleep(min(0.1, end_time - time.time()))

    def _resolve_value(self, token: str) -> float:
        """Resolve token = number hoặc variable name."""
        try:
            return float(token)
        except ValueError:
            return self._variables.get(token, 0)



# ---------------------------------------------------------------------------
#  Utilities
# ---------------------------------------------------------------------------

def _tokenize(line: str) -> list[str]:
    """Tách tokens, giữ nguyên chuỗi trong quotes."""
    tokens = []
    i = 0
    while i < len(line):
        if line[i] in (" ", "\t"):
            i += 1
            continue
        if line[i] in ("'", '"'):
            quote = line[i]
            j = line.index(quote, i + 1) + 1
            tokens.append(line[i:j])
            i = j
        else:
            j = i
            while j < len(line) and line[j] not in (" ", "\t"):
                j += 1
            tokens.append(line[i:j])
            i = j
    return tokens


def _find_matching_end(lines: list[str], start: int) -> int:
    """Tìm dòng 'end' tương ứng với loop/if ở dòng start."""
    depth = 0
    for i in range(start, len(lines)):
        tok0 = _tokenize(lines[i])[0].lower()
        if tok0 in ("loop", "if", "do"):
            depth += 1
        elif tok0 in ("end", "until"):
            depth -= 1
            if depth == 0:
                return i
    raise DSLError(f"Missing 'end' for block starting at line {start + 1}")


def _find_matching_until(lines: list[str], start: int) -> int:
    """Tìm dòng 'until' tương ứng với 'do' ở dòng start."""
    depth = 0
    for i in range(start, len(lines)):
        tok0 = _tokenize(lines[i])[0].lower()
        if tok0 in ("loop", "if", "do"):
            depth += 1
        elif tok0 in ("end", "until"):
            depth -= 1
            if depth == 0:
                if tok0 != "until":
                    raise DSLError(f"Expected 'until' for 'do' at line {start + 1}, got '{tok0}' at line {i + 1}")
                return i
    raise DSLError(f"Missing 'until' for 'do' at line {start + 1}")


# Virtual key mapping
_VK_MAP = {
    "enter": win32con.VK_RETURN, "return": win32con.VK_RETURN,
    "space": win32con.VK_SPACE, "tab": win32con.VK_TAB,
    "escape": win32con.VK_ESCAPE, "esc": win32con.VK_ESCAPE,
    "backspace": win32con.VK_BACK, "delete": win32con.VK_DELETE,
    "up": win32con.VK_UP, "down": win32con.VK_DOWN,
    "left": win32con.VK_LEFT, "right": win32con.VK_RIGHT,
    "home": win32con.VK_HOME, "end": win32con.VK_END,
    "pageup": win32con.VK_PRIOR, "pagedown": win32con.VK_NEXT,
    "f1": win32con.VK_F1, "f2": win32con.VK_F2, "f3": win32con.VK_F3,
    "f4": win32con.VK_F4, "f5": win32con.VK_F5, "f6": win32con.VK_F6,
    "f7": win32con.VK_F7, "f8": win32con.VK_F8, "f9": win32con.VK_F9,
    "f10": win32con.VK_F10, "f11": win32con.VK_F11, "f12": win32con.VK_F12,
    "shift": win32con.VK_SHIFT, "ctrl": win32con.VK_CONTROL,
    "alt": win32con.VK_MENU,
}


def _key_name_to_vk(name: str) -> Optional[int]:
    lower = name.lower()
    if lower in _VK_MAP:
        return _VK_MAP[lower]
    if len(name) == 1:
        return ord(name.upper())
    return None
