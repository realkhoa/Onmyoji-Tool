import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from pps_engine.screenshot import WindowCapture

class CaptureWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._capture: WindowCapture | None = None
        self._mutex = QMutex()
        self._fps = 15  # default

    def set_fps(self, fps: int):
        """Adjust capture frame rate (frames per second)."""
        with QMutexLocker(self._mutex):
            self._fps = max(1, fps)

    def set_capture(self, cap: WindowCapture | None):
        with QMutexLocker(self._mutex):
            self._capture = cap

    def run(self):
        self._running = True
        while self._running:
            with QMutexLocker(self._mutex):
                cap = self._capture
            if cap:
                try:
                    frame = cap.capture()
                    if frame is not None:
                        self.frame_ready.emit(frame)
                except Exception:
                    pass
            # sleep based on current fps setting
            with QMutexLocker(self._mutex):
                fps = self._fps
            interval = int(1000 / fps) if fps > 0 else 67
            self.msleep(interval)

    def stop(self):
        self._running = False
        self.wait()
