from __future__ import annotations

from dataclasses import dataclass, field

import xbmc
import xbmcgui

from modules.kodi_utils import (
    log,
    kodi_window,
)
from modules.player import NASPlayer


@dataclass
class NASMonitor(xbmc.Monitor):
    window: xbmcgui.Window = field(init=False)
    player: NASPlayer = field(init=False, default_factory=NASPlayer)

    def __post_init__(self):
        log("NASMonitor Service Starting")
        self.window = kodi_window()
        self.waitForAbort()
        log("NASMonitor Service Finished")


NASMonitor()
