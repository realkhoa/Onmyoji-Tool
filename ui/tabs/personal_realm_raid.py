from ui.tabs.feature_tab import FeatureTab

class PersonalRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title_key="tab_personal_raid",
            desc_key="desc_personal_raid",
            default_dsl="dsl/builtin/personal_realm_raid.dsl",
            parent=parent,
        )
