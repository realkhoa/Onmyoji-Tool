---
name: Onmyoji Bot Developer
description: Guidelines and instructions for working on the Onmyoji-Tool repository.
---

# Onmyoji Bot Developer Guide

You are an expert Python developer working on the `Onmyoji-Tool` project. Ensure you follow these strict project conventions when responding to the user or making changes.

## 1. UI Refactoring and Structure (PyQt6)
- **Framework**: Use `PyQt6` exclusively. Avoid snippets intended for PyQt5, PySide2, or PySide6.
- **Component Isolation**: If a user requests a new tab or significant dialog widget, place it entirely inside its own `.py` file under `ui/tabs/` or `ui/comps/`. Keep `main.py` clean.
- **Responsive Design**: Avoid absolute positioning (`move()` or `setGeometry()`) for complex widgets. Rely on standard layout managers (`QVBoxLayout`, `QHBoxLayout`, `QGridLayout`) combined with size policies.

## 2. Localization (i18n)
- **Never Hardcode Text**: All user-facing strings in Python files must be wrapped inside `t("translation_key")`. The `t` function is imported from `i18n.py`.
- **JSON Maintenance**: If you introduce a new translation key, you must add it to *all* JSON dictionaries within the `locales/` folder (`en_US.json`, `vi_VN.json`, `fr_FR.json`, `zh_CN.json`).

## 3. Automation Engine (`pps_engine`)
- **No Physical Mouse Locks**: NEVER use libraries like `pyautogui`, `keyboard`, or `mouse` which require physical foreground control of the mouse schema.
- **Background Actions**: All clicks and inputs MUST be routed to the specific game window handle (`HWND`) using `win32api.MAKELONG` and `win32gui.PostMessage`. 
- **Screen Capturing**: Screenshots are pulled from background memory using PyWin32 GDI functions (`BitBlt`), specifically implemented inside `screenshot.py`. Use this abstraction rather than naive screen grabbing tools like `Pillow.ImageGrab`.

## 4. Packing and Compilation
- **PyInstaller Bundles**: The codebase uses `build.py` to bundle to an executable.
- **Path Resolution**: When you load a local image, script, or JSON file, always resolve paths relative to `BASE_DIR`. 
   - *Example:* `BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))`
- **Dependencies**: New folders/assets must be explicitly added as arguments (e.g., `--add-data path:path`) inside the `build.py` script.
