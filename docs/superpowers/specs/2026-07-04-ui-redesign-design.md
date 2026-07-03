# UI Redesign Specification - Onmyoji Bot

This document outlines the design and technical specification for redoing the PyQt6 user interface of the `Onmyoji-Tool` application to achieve a premium gaming aesthetic and improve user experience (UX).

## 1. Goal Description

The current user interface is using a basic, unstyled layout with a horizontal tab bar that becomes cluttered and scrolls awkwardly when multiple feature tabs are added. Additionally, there is a tab indexing bug where the "Khác" (Others) tab gets misnamed when changing languages due to nested tab structures.

This redesign:
1. Replaces the horizontal tab bar with a vertical sidebar on the left.
2. Flat-lists all 10 feature tabs to simplify navigation and resolve the indexing bug.
3. Applies a modern "Ruby Gaming" Dark Theme stylesheet (QSS) with charcoal backgrounds and crimson/ruby red accents.
4. Redesigns the connection panel to reside in the sidebar with an LED status indicator.
5. Implements custom styling for inputs, group boxes, buttons, scrollbars, and splitters.

## 2. Component Design & Changes

### Left Sidebar Navigation Panel
- **Widget**: `QFrame` named `sidebar_frame` (fixed width: `220px`).
- **Logo Area**: A bold `QLabel` with text "ONMYOJI BOT" in uppercase, colored `#e11d48` (crimson red), and a small subtitle "Automation Engine".
- **Navigation Menu**: A `QListWidget` named `sidebar_list`. Items will have custom padding, rounded corners, icons, and text.
- **Connection Panel**: Positioned at the bottom of the sidebar. It contains:
  - An LED indicator `QLabel` (`conn_status_dot`) styled as a small green/red circle.
  - Connection text label (`_window_lbl`).
  - Auto-connect checkbox (`_chk_auto`).
  - A flat action button (`_btn_manual_attach`) to connect/disconnect.

### Right Content Panel
- **Top Header**: A thin horizontal layout containing the language switcher (`_lang_combo`) and the manual process dropdown/refresh buttons.
- **Main Splitter**:
  - **Left**: Game Preview groupbox containing the `PreviewLabel` and its toggle/coordinates labels.
  - **Right**: `QStackedWidget` containing the settings for the active feature.
- **Bottom**: Activity log groupbox with the clear button and logs text area.

### Flat-Listing of Features
To solve the indexing bug and clean up navigation:
- Remove `OthersTab` completely.
- Add `ScriptConsoleTab`, `GuideTab`, and the `ComingSoonTab` ("Khác") directly to the main stacked widget and sidebar menu.
- Ensure the main index array matches the 10 tabs exactly, aligning perfectly with the translation files:
  1. Tiện ích (Utils)
  2. Kết giới Guild (Guild Realm Raid)
  3. Kết giới Cá nhân (Personal Realm Raid)
  4. Auto Click
  5. Treo rắn (Soul)
  6. Bách Quỷ (Demon Parade)
  7. PVP (Auto Duel)
  8. CLI (Console)
  9. Guide (Hướng dẫn)
  10. Khác (Others Placeholder)

## 3. Stylesheet (QSS) Architecture (`ui/style.py`)

A comprehensive QSS stylesheet will be implemented in `ui/style.py`:

```css
/* Core Colors */
/* Background: #0d0d0f (Deep charcoal) */
/* Cards/GroupBoxes: #18181b */
/* Accent: #be123c (Ruby/Crimson) */
/* Hover Accent: #e11d48 (Light Crimson) */
/* Borders: #27272a */

QMainWindow {
    background-color: #0d0d0f;
}

QWidget {
    color: #f4f4f5;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QFrame#sidebar_frame {
    background-color: #121214;
    border-right: 1px solid #27272a;
}

QListWidget#sidebar_list {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#sidebar_list::item {
    height: 38px;
    padding-left: 12px;
    color: #a1a1aa;
    border-radius: 6px;
    margin: 3px 8px;
}

QListWidget#sidebar_list::item:hover {
    background-color: #1e1b1b;
    color: #f4f4f5;
}

QListWidget#sidebar_list::item:selected {
    background-color: #be123c;
    color: #ffffff;
    font-weight: bold;
}

QGroupBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 15px;
    padding-top: 15px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 5px;
    color: #f4f4f5;
    font-weight: bold;
}

QPushButton {
    background-color: #18181b;
    border: 1px solid #27272a;
    color: #e4e4e7;
    border-radius: 6px;
    padding: 6px 15px;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #27272a;
    border-color: #3f3f46;
}

QPushButton:pressed {
    background-color: #09090b;
}

QPushButton#btn_success {
    background-color: #be123c;
    border: 1px solid #e11d48;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#btn_success:hover {
    background-color: #e11d48;
    border-color: #fda4af;
}

QPushButton#btn_danger {
    background-color: #1c1917;
    border: 1px solid #be123c;
    color: #f43f5e;
}

QPushButton#btn_danger:hover {
    background-color: #be123c;
    color: #ffffff;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #e4e4e7;
    padding: 4px 8px;
    min-height: 26px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #be123c;
}

QScrollBar:vertical {
    background-color: #0d0d0f;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #27272a;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #be123c;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
```

## 4. Verification Plan

### Automated Verification
Run the python app locally to verify successful launch and UI interactions:
```bash
python main.py
```
Check that:
- The app starts without syntax errors or runtime exceptions.
- The sidebar displays all 10 features with correct names and icons.
- Clicking sidebar items switches the active configuration stacked widget correctly.
- Disconnecting and connecting updates the LED light indicator and text.
- Language switching updates all sidebar item labels without naming bugs.

### Manual Verification
- Resize the main window to check responsive behaviors of the sidebar and splitter.
- Verify that double-clicking on the preview screen registers the coordinates in the Auto Click tab correctly.
- Verify that logs are printed correctly to the log panel.
