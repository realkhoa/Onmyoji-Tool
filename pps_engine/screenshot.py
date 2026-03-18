import logging
import time
import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
PrintWindow = user32.PrintWindow

# Refresh the window rect at most once per this many seconds.
_RECT_CACHE_TTL = 0.5


class WindowCapture:

    def __init__(self, window_name):

        self.hwnd = win32gui.FindWindow(None, window_name)

        if not self.hwnd:
            raise Exception("Window not found")

        self._rect_cache_time = 0.0
        self.update_window_rect()

    def update_window_rect(self):
        rect = win32gui.GetClientRect(self.hwnd)
        self.w = max(1, rect[2])
        self.h = max(1, rect[3])

        client_pos = win32gui.ClientToScreen(self.hwnd, (0, 0))
        self.x = client_pos[0]
        self.y = client_pos[1]
        self._rect_cache_time = time.monotonic()

    def capture(self):
        # Only refresh position/size when the cached value is stale.
        if time.monotonic() - self._rect_cache_time > _RECT_CACHE_TTL:
            self.update_window_rect()

        hwndDC = win32gui.GetWindowDC(self.hwnd)
        if not hwndDC:
            logger.warning("GetWindowDC returned 0 for hwnd=%s", self.hwnd)
            return None

        mfcDC = saveDC = bitmap = None
        img = None
        result = 0
        try:
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfcDC, self.w, self.h)
            saveDC.SelectObject(bitmap)

            result = PrintWindow(
                self.hwnd,
                saveDC.GetSafeHdc(),
                3
            )

            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)

            img = np.frombuffer(bmpstr, dtype=np.uint8)
            img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
            img = img[..., :3]
        except Exception as exc:
            logger.error("Window capture failed: %s", exc)
            img = None
            result = 0
        finally:
            if bitmap is not None:
                win32gui.DeleteObject(bitmap.GetHandle())
            if saveDC is not None:
                saveDC.DeleteDC()
            if mfcDC is not None:
                mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwndDC)

        if result != 1:
            return None

        return img
