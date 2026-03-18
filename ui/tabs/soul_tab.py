from pathlib import Path
from PyQt6.QtWidgets import QComboBox
from ui.tabs.feature_tab import FeatureTab

class SoulTab(FeatureTab):
    """Tab treo rắn. Có selector chủ phòng / được mời, thay đổi script accordingly."""
    def __init__(self, parent=None):
        # default to host
        super().__init__(
            title_key="tab_soul",
            desc_key="desc_soul",
            default_dsl="dsl/builtin/auto_soul.dsl",
            parent=parent,
        )
