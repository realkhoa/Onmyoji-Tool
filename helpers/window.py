import win32gui

GAME_WINDOW_KEYWORDS = ["陰陽師Onmyoji"]

def find_game_window() -> str | None:
    """Tìm cửa sổ game theo keyword. Trả về tên cửa sổ hoặc None."""
    found = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        for kw in GAME_WINDOW_KEYWORDS:
            if kw in title:
                found.append(title)
                return

    win32gui.EnumWindows(_cb, None)
    return found[0] if found else None
