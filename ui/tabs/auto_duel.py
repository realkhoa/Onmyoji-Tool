from ui.tabs.feature_tab import FeatureTab

class AutoDuelTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title_key="tab_pvp",
            desc_key="desc_pvp",
            default_dsl="dsl/builtin/auto_duel.dsl",
            parent=parent,
        )
