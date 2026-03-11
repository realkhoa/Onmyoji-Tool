from pathlib import Path
from PyQt6.QtWidgets import QComboBox
from ui.tabs.feature_tab import FeatureTab
from i18n import t

class SoulTab(FeatureTab):
    """Tab treo rắn. Có selector chủ phòng / được mời, thay đổi script accordingly."""
    def __init__(self, parent=None):
        # default to host
        super().__init__(
            title="🐍 Treo rắn",
            description=t("desc_soul"),
            default_dsl="dsl/builtin/auto_soul_host.dsl",
            parent=parent,
        )
        # insert combo right after header
        root = self.layout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([t("mode_host"), t("mode_invited")])
        self._mode_combo.setMaxVisibleItems(10)
        self._mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._mode_combo.currentIndexChanged.connect(self._mode_changed)
        # combo should appear before the description label (index 1)
        root.insertWidget(1, self._mode_combo)

    def _mode_changed(self, idx: int):
        if idx == 0:
            self._dsl_file = Path("dsl/builtin/auto_soul_host.dsl")
        else:
            self._dsl_file = Path("dsl/builtin/auto_soul_invited.dsl")
        self._file_lbl.setText(self._dsl_file.name)
