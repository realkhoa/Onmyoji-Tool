from ui.tabs.feature_tab import FeatureTab
from i18n import t

class GuildRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔ Phá kết giới guild",
            description=t("desc_guild_raid"),
            default_dsl="dsl/builtin/guild_realm_raid.dsl",
            parent=parent,
        )
