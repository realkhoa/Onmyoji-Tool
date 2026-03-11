from ui.tabs.feature_tab import FeatureTab
from i18n import t

class AutoDemonParadeTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="🎯 Ném đậu (Bách Quỷ Dạ Hành)",
            description=t("desc_demon_parade"),
            default_dsl="dsl/builtin/auto_demon_parade.dsl",
            parent=parent,
        )
