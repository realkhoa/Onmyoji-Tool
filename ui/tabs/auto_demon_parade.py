from ui.tabs.feature_tab import FeatureTab

class AutoDemonParadeTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title_key="tab_demon_parade",
            desc_key="desc_demon_parade",
            default_dsl="dsl/builtin/auto_demon_parade.dsl",
            parent=parent,
        )
