from ui.tabs.feature_tab import FeatureTab
from i18n import t

class AutoDuelTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔️ PVP",
            description=t("desc_pvp"),
            default_dsl="dsl/builtin/auto_duel.dsl",
            parent=parent,
        )
