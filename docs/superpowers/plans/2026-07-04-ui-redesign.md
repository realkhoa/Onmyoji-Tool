# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Onmyoji Bot user interface to feature a modern vertical left sidebar layout, apply a premium gaming-style crimson/ruby dark theme, and fix the tab indexing language bug by flat-listing all tabs.

**Architecture:** Re-architect the main window central layout from a top-tab/left-preview layout to a left-sidebar/right-content layout. The sidebar uses a styled QListWidget for horizontal text vertical-tab selection, linked to the central stacked widget. A global QSS stylesheet is applied.

**Tech Stack:** PyQt6, Python 3.11

## Global Constraints
- PyQt6 exclusively
- Component Isolation: No absolute positioning for main layouts, rely on layouts/QSplitter
- Localization: All user-facing strings must support i18n
- No physical mouse locks, use background click/screenshot actions as currently structured

---

### Task 1: Stylesheet Implementation

**Files:**
- Modify: `ui/style.py:1-16`

**Interfaces:**
- Produces: `APP_STYLE` global stylesheet string used by `main()` in `main.py`

- [ ] **Step 1: Replace stylesheet content with premium QSS**
  Write the following content to `ui/style.py`, replacing the existing very simple style:

```python
APP_STYLE = """
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
    border-right: 1px solid #1f1f23;
}

QLabel#sidebar_title {
    font-size: 18px;
    font-weight: bold;
    color: #e11d48;
}

QLabel#sidebar_subtitle {
    font-size: 10px;
    color: #71717a;
}

QListWidget#sidebar_list {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#sidebar_list::item {
    height: 38px;
    padding-left: 8px;
    color: #a1a1aa;
    border-radius: 6px;
    margin: 2px 6px;
}

QListWidget#sidebar_list::item:hover {
    background-color: #1c1917;
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
    margin-top: 14px;
    padding-top: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    color: #e4e4e7;
    font-weight: bold;
}

QPushButton {
    background-color: #18181b;
    border: 1px solid #27272a;
    color: #e4e4e7;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 26px;
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

QPushButton#btn_success:pressed {
    background-color: #9f1239;
}

QPushButton#btn_danger {
    background-color: #1c1917;
    border: 1px solid #be123c;
    color: #f43f5e;
    font-weight: bold;
}

QPushButton#btn_danger:hover {
    background-color: #be123c;
    color: #ffffff;
}

QPushButton#btn_danger:pressed {
    background-color: #9f1239;
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

QComboBox::drop-down {
    border: none;
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

QSplitter::handle {
    background-color: #18181b;
}

QSplitter::handle:horizontal {
    width: 2px;
}
"""
```

- [ ] **Step 2: Commit**
  Run:
  ```bash
  git add ui/style.py
  git commit -m "style: implement dark ruby QSS theme"
  ```

---

### Task 2: Layout Re-architecture in `main.py`

**Files:**
- Modify: `main.py:107-329`
- Modify: `main.py:461-516`
- Modify: `main.py:350-361`
- Delete: `ui/tabs/others_tab.py`

**Interfaces:**
- Consumes: `ui.style.APP_STYLE`
- Modifies: `ToolsWindow` initialization and layout setup.

- [ ] **Step 1: Redesign `_init_ui` layout**
  Update `_init_ui` in `main.py` (lines 107-313 approx) to:
  1. Create a `QHBoxLayout` for the central widget.
  2. Create a `QFrame` named `self._sidebar_frame` with object name `sidebar_frame` and fixed width `220`.
  3. Inside `sidebar_frame`, layout a `QVBoxLayout` with margins `12, 16, 12, 16`:
     - Logo Area:
       - `self._logo_title = QLabel("ONMYOJI BOT")` (object name `sidebar_title`)
       - `self._logo_sub = QLabel("Automation Engine")` (object name `sidebar_subtitle`)
     - Navigation:
       - `self._sidebar_list = QListWidget()` (object name `sidebar_list`)
       - Add 10 items to `self._sidebar_list` representing all tabs:
         - "🛠 Tiện ích"
         - "⚔ Kết giới Guild"
         - "⚔ Kết giới Cá nhân"
         - "🖱 Auto Click"
         - "🐍 Treo rắn"
         - "🎯 Bách Quỷ"
         - "⚔️ PVP"
         - "💻 CLI"
         - "📚 Guide"
         - "➕ Khác"
       - Connect: `self._sidebar_list.currentRowChanged.connect(self._on_tab_changed)`
     - Connection Status Panel (moved to bottom of sidebar):
       - A `QFrame` for connection info containing:
         - A horizontal layout with:
           - A status LED circle `self._conn_led = QLabel()` with fixed size `8x8` and object name `conn_status_led`.
           - `self._window_lbl = QLabel(t("status_disconnected"))` (object name `window_label`).
         - A checkbox `self._chk_auto = QCheckBox()` (tool tip `auto_connect_tooltip`).
         - A button `self._btn_manual_attach = QPushButton(t("btn_connect"))` (which connects/disconnects).
  4. Create a main right content area (`QWidget`) with a `QVBoxLayout`:
     - Top Header: A horizontal layout containing the language switcher (`self._lang_combo`) and process selection widgets (shown when auto-connect is off): `self._proc_combo` and `self._btn_refresh_proc`.
     - Splitter (Horizontal):
       - Left: Preview Pane (`left` widget containing Game Screen groupbox and `PreviewLabel`).
       - Right: `QStackedWidget` (`self._stack`).
     - Bottom: Activity Log Panel.

- [ ] **Step 2: Flat-list features and remove `OthersTab`**
  Modify lines 240-288 (approx) in `main.py`:
  - Completely remove creation/usage of `OthersTab`.
  - Add CLI, Guide, and ComingSoonTab directly to the stacked widget with `nested=False` via `_add_feature_tab`.
  The addition order MUST be:
  ```python
  self._tab_utils = UtilsTab()
  self._add_feature_tab(self._tab_utils, "Utils") # index 0

  self._tab_guild = GuildRealmRaidTab()
  self._tab_guild.set_engine(self._engine)
  self._add_feature_tab(self._tab_guild, "Guild") # index 1

  self._tab_personal = PersonalRealmRaidTab()
  self._tab_personal.set_engine(self._engine)
  self._add_feature_tab(self._tab_personal, "Personal") # index 2

  self._tab_autoclick = AutoClickTab()
  # (Connect preview signals to autoclick)
  self._add_feature_tab(self._tab_autoclick, "AutoClick") # index 3

  self._tab_soul = SoulTab()
  self._tab_soul.set_engine(self._engine)
  self._add_feature_tab(self._tab_soul, "Soul") # index 4

  self._tab_demon_parade = AutoDemonParadeTab()
  self._tab_demon_parade.set_engine(self._engine)
  self._add_feature_tab(self._tab_demon_parade, "DemonParade") # index 5

  self._tab_auto_duel = AutoDuelTab()
  self._tab_auto_duel.set_engine(self._engine)
  self._add_feature_tab(self._tab_auto_duel, "PVP") # index 6

  self._tab_console = ScriptConsoleTab()
  self._tab_console.set_engine(self._engine)
  self._add_feature_tab(self._tab_console, "CLI") # index 7

  self._tab_guide = GuideTab()
  self._add_feature_tab(self._tab_guide, "Guide") # index 8

  self._coming_soon = ComingSoonTab("Tính năng khác")
  self._add_feature_tab(self._coming_soon, "Others") # index 9
  ```

- [ ] **Step 3: Update frame handler and close events**
  In `main.py`:
  - Update `_on_frame` to:
  ```python
    def _on_frame(self, frame: np.ndarray):
        self._preview.update_frame(frame)
        curr_tab = self._stack.currentWidget()
        for tab in self._feature_tabs:
            if tab == curr_tab or tab.is_running():
                tab.set_last_frame(frame)
  ```
  - In `_on_tab_changed`:
  ```python
    def _on_tab_changed(self, index: int):
        if self._prev_tab_idx != -1:
            prev_tab = self._stack.widget(self._prev_tab_idx)
            if hasattr(prev_tab, "on_deactivated"):
                prev_tab.on_deactivated()
        
        self._stack.setCurrentIndex(index)
        curr_tab = self._stack.widget(index)
        if hasattr(curr_tab, "on_activated"):
            curr_tab.on_activated()
        
        self._prev_tab_idx = index
  ```

- [ ] **Step 4: Update status and LED indicator styles**
  In `_do_attach` and `_do_detach`, update the status LED property and polish style:
  ```python
  # Connected
  self._conn_led.setProperty("status", "connected")
  self._conn_led.style().unpolish(self._conn_led)
  self._conn_led.style().polish(self._conn_led)
  # Disconnected
  self._conn_led.setProperty("status", "disconnected")
  self._conn_led.style().unpolish(self._conn_led)
  self._conn_led.style().polish(self._conn_led)
  ```
  Add connection LED style rules to `APP_STYLE`:
  ```css
  QLabel#conn_status_led {
      min-width: 8px;
      min-height: 8px;
      max-width: 8px;
      max-height: 8px;
      border-radius: 4px;
      margin-right: 6px;
  }
  QLabel#conn_status_led[status="connected"] {
      background-color: #22c55e;
  }
  QLabel#conn_status_led[status="disconnected"] {
      background-color: #71717a;
  }
  ```

- [ ] **Step 5: Clean up nested imports and unused files**
  Delete the nested tab widget class file `ui/tabs/others_tab.py`.
  Run:
  ```bash
  git rm ui/tabs/others_tab.py
  ```

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add main.py ui/style.py
  git commit -m "feat: re-architect main window with vertical sidebar navigation"
  ```

---

### Task 3: Localization Update and Language Switching Fix

**Files:**
- Modify: `main.py:336-361`

**Interfaces:**
- Consumes: `i18n.t`
- Modifies: `ToolsWindow.update_texts`

- [ ] **Step 1: Implement `update_texts` logic for sidebar QListWidget**
  Update `update_texts` to set text directly in the sidebar items, keeping icons:
  ```python
    def update_texts(self, lang=None):
        self.setWindowTitle(t("app_title"))
        self._proc_combo.setToolTip(t("tooltip_proc_combo"))
        self._btn_refresh_proc.setToolTip(t("tooltip_refresh_proc"))
        if self._capture:
            self._window_lbl.setText(t("status_connected", name=self._log_name if hasattr(self, '_log_name') else "Onmyoji"))
            self._btn_manual_attach.setText(t("btn_disconnect"))
        else:
            self._window_lbl.setText(t("status_disconnected"))
            self._btn_manual_attach.setText(t("btn_connect"))
            
        self._chk_auto.setToolTip(t("auto_connect_tooltip"))
        self._chk_preview.setText(t("preview_toggle"))
        
        # Update sidebar items with localized text and icons
        self._sidebar_list.item(0).setText("🛠 " + t("tab_utils"))
        self._sidebar_list.item(1).setText("⚔ " + t("tab_guild_raid"))
        self._sidebar_list.item(2).setText("⚔ " + t("tab_personal_raid"))
        self._sidebar_list.item(3).setText("🖱 " + t("tab_autoclick"))
        self._sidebar_list.item(4).setText("🐍 " + t("tab_soul"))
        self._sidebar_list.item(5).setText("🎯 " + t("tab_demon_parade"))
        self._sidebar_list.item(6).setText("⚔️ " + t("tab_pvp"))
        self._sidebar_list.item(7).setText("💻 " + t("tab_cli"))
        self._sidebar_list.item(8).setText("📚 " + t("tab_guide"))
        self._sidebar_list.item(9).setText("➕ " + t("tab_others"))
  ```

- [ ] **Step 2: Commit**
  Run:
  ```bash
  git add main.py
  git commit -m "fix: translate sidebar list items and fix language switching indexing bug"
  ```
