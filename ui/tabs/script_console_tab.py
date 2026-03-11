import threading
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QFileDialog
from ui.tabs.feature_tab import FeatureTab
from ui.comps.line_number_area import LineNumberEditor
from i18n import t

class ScriptConsoleTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="💻 CLI",
            description=t("desc_cli"),
            default_dsl="",  # start empty
            parent=parent,
        )
        # hide file selector since CLI uses direct editor
        try:
            self._file_lbl.hide()
            self._btn_browse.hide()
        except AttributeError:
            pass
        # insert editor area
        layout = self.layout()
        self.script_edit = LineNumberEditor()
        self.script_edit.setObjectName("script_editor")
        self.script_edit.setPlaceholderText(t("placeholder_dsl"))
        layout.insertWidget(2, self.script_edit, 1)
        # load/save buttons below editor
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton(t("btn_load"))
        self.btn_save = QPushButton(t("btn_save"))
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        layout.insertLayout(3, btn_row)

        self.btn_load.clicked.connect(self._load)
        self.btn_save.clicked.connect(self._save)

        self._worker_thread: threading.Thread | None = None

    def _start(self):
        # override FeatureTab behaviour to read from editor
        if self._running:
            return
        if self._engine._capture is None:
            self._set_status("⚠ Chưa attach cửa sổ game!", "#e22134")
            self.log_signal.emit("[Console] Chưa attach cửa sổ game.")
            return
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.log_signal.emit("[Console] " + t("msg_script_empty"))
            return
        self._running = True
        self._engine.reset_stop()
        self._btn_start.hide()
        self._btn_stop.show()
        self._set_status("⟳ Đang chạy...", "#1db954")
        self.started_signal.emit()
        self._worker_thread = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker_thread.start()
        self.log_signal.emit("[Console] " + t("msg_running_script"))

    def _run(self, script: str):
        try:
            self._engine.execute(script, log_fn=lambda msg: self.log_signal.emit(f"[Console] {msg}"))
        except Exception as e:
            self.log_signal.emit(f"[Console] Lỗi: {e}")
        finally:
            self._running = False
            self._on_stopped()

    def _stop(self):
        self._engine.request_stop()
        self._running = False
        self._on_stopped()

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, t("title_load_script"), "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.script_edit.setPlainText(f.read())

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, t("title_save_script"), "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.script_edit.toPlainText())
