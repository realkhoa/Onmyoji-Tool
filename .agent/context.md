# Onmyoji-Tool Context

## Project Overview
This project is an automation tool (bot) designed for the game Onmyoji (Âm Dương Sư) on Windows. It avoids invasive hooks, preferring computer vision via OpenCV and background window commands using Win32 API interactions. This allows the user to leave the game running in the background while using their computer normally.

## Technology Stack
- **Language**: Python 3.10+
- **UI Framework**: PyQt6 (styled with `qt-material`)
- **Image Processing**: `opencv-python` (cv2), `numpy`
- **System API**: `pywin32` (win32gui, win32api, win32con, win32ui for memory captures)
- **Packaging**: PyInstaller (`build.py`)

## Core Architecture & Components
The tool is built with modularity and extensibility in mind.
- `main.py`: The entry point. Handles the main GUI loop and loads interface modules.
- `ui/`: Contains all PyQt6 elements.
  - `ui/tabs/`: Contains separated UI classes for every specific feature (e.g. `AutoClickTab`, `ScriptConsoleTab`, `GuildRealmRaidTab`). These rely on the core engine.
  - `ui/comps/`: Contains reusable elements like custom toggles, numeric editors, and customized widgets.
- `pps_engine/`: The core Domain Specific Language (DSL) execution engine framework. It interprets `.dsl` scripts containing commands (e.g., Click, Wait, FindTemplate) and runs them in a background thread.
- `helpers/`: Utilities that support broader operations, such as locating the game window (`window.py`) and grabbing frames from memory asynchronously (`capture.py`).
- `dsl/`: Directory containing all `.dsl` automation scripts and their corresponding `.png` template images used for pattern matching.
- `locales/`: Stores `.json` string resources (en_US, vi_VN, fr_FR, zh_CN) for internationalization (i18n).

## Key Concepts
1. **Background PostMessage Handling**: Mouse clicks must use `win32gui.PostMessage(hwnd, WM_LBUTTONDOWN, ...)` so they do not steal the user's physical mouse cursor.
2. **DSL Driven Automation**: The engine doesn't hardcode logic inside Python files. Instead, it reads customizable `.dsl` text scripts so users can easily edit logic on the fly without needing programming experience.
3. **i18n Translation**: Text within the user interface must be translated through `i18n.py`'s `t("string_key")` method. Hardcoding strings in Python is heavily discouraged.
4. **PyInstaller Compatibility**: Because the application gets compiled to `.exe`, paths to bundled assets (like default `dsl/` folders or `locales/`) must use `sys._MEIPASS` when running in a frozen bundle. This is typically managed via `BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))`.
