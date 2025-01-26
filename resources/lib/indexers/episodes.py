import sys
from dataclasses import dataclass, field

from xbmcplugin import addDirectoryItems, setContent, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioMeta import StremioMeta, Video, StremioType
from indexers.base_indexer import BaseIndexer
from modules.utils import build_url, KodiDirectoryType


@dataclass
class Episodes(BaseIndexer[Video]):
    content_id: str
    content_type: str
    season: int
    series: StremioMeta = field(init=False)

    def __post_init__(self):
        handle = int(sys.argv[1])

        self.series = stremio_api.get_metadata_by_id(self.content_id, self.content_type)

        addDirectoryItems(handle, [i for i in self._worker(self.series.videos) if i])
        setContent(handle, KodiDirectoryType.EPISODES)
        setPluginCategory(
            handle, f"Season {self.season}" if self.season else "Specials"
        )
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: Video, position):
        if item.season != self.season and self.season >= 0:
            return

        list_item = item.build_list_item()

        url_params = build_url(
            {
                "mode": "playback",
                "func": "media",
                "content_id": self.series.id,
                "content_type": self.series.type,
                "episode": position,
            }
        )

        return url_params, list_item, False
