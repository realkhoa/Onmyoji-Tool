from ui.tabs.feature_tab import FeatureTab
from i18n import t

class PersonalRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔ Phá kết giới cá nhân",
            description=t("desc_personal_raid"),
            default_dsl="dsl/builtin/personal_realm_raid.dsl",
            parent=parent,
        )
