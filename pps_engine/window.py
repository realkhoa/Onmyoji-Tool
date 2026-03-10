import time
import ctypes
import ctypes.wintypes
import win32api
import win32con
import win32gui
from typing import Optional

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

class WindowMixin:
    def _window_click(self, x: int, y: int, button="left", double=False):
        with self._lock:
            cap = self._capture
        if cap is None:
            return
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
        with self._lock:
            cap = self._capture
        if cap is None:
            return
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
        with self._lock:
            cap = self._capture
        if cap is None:
            return
        hwnd = cap.hwnd
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        has_menu = win32gui.GetMenu(hwnd) != 0
        rect = ctypes.wintypes.RECT(0, 0, width, height)
        ctypes.windll.user32.AdjustWindowRectEx(
            ctypes.byref(rect), style, has_menu, ex_style
        )
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        cur_rect = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(hwnd, cur_rect[0], cur_rect[1], win_w, win_h, True)
