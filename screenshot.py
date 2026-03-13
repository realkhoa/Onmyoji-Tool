import win32gui
import win32ui
import win32con
import numpy as np
import cv2
import ctypes

user32 = ctypes.windll.user32
PrintWindow = user32.PrintWindow

class WindowCapture:

    def __init__(self, window_name):

        self.hwnd = win32gui.FindWindow(None, window_name)

        if not self.hwnd:
            raise Exception("Window not found")

        self.update_window_rect()

    def update_window_rect(self):
        rect = win32gui.GetClientRect(self.hwnd)
        self.w = max(1, rect[2])
        self.h = max(1, rect[3])

        client_pos = win32gui.ClientToScreen(self.hwnd, (0, 0))
        self.x = client_pos[0]
        self.y = client_pos[1]

    def capture(self):
        self.update_window_rect()

        hwndDC = win32gui.GetWindowDC(self.hwnd)
        if not hwndDC:
            return None
        
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        try:
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
        except Exception:
            img = None
            result = 0

        win32gui.DeleteObject(bitmap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwndDC)

        if result != 1:
            return None

        return img