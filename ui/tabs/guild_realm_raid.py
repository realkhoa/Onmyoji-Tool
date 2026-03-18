from ui.tabs.feature_tab import FeatureTab


class GuildRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title_key="tab_guild_raid",
            desc_key="desc_guild_raid",
            default_dsl="dsl/builtin/guild_realm_raid.dsl",
            parent=parent,
        )
