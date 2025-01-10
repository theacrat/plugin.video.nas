from dataclasses import dataclass
from functools import cached_property

import xbmcaddon


@dataclass
class NASAddon(xbmcaddon.Addon):
    @cached_property
    def name(self):
        return self.getAddonInfo("id")

    @cached_property
    def version(self):
        return self.getAddonInfo("version")

    @cached_property
    def path(self):
        return self.getAddonInfo("path")

    @cached_property
    def icon(self):
        return self.getAddonInfo("icon")

    @cached_property
    def fanart(self):
        return self.getAddonInfo("fanart")

    @cached_property
    def profile(self):
        from xbmcvfs import translatePath

        return translatePath(self.getAddonInfo("profile"))


nas_addon = NASAddon()
