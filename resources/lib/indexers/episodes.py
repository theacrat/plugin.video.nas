import sys
from dataclasses import dataclass, field

from xbmcplugin import addDirectoryItems, setContent, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioMeta import StremioMeta, Video
from indexers.base_indexer import BaseIndexer
from modules.kodi_utils import build_url


@dataclass
class Episodes(BaseIndexer[Video]):
    id: str
    season: int
    series: StremioMeta = field(init=False)

    def __post_init__(self):
        handle = int(sys.argv[1])

        self.series = stremio_api.get_metadata_by_id(self.id, "series")

        addDirectoryItems(handle, [i for i in self._worker(self.series.videos) if i])
        setContent(handle, "episodes")
        setPluginCategory(
            handle, f"Season {self.season}" if self.season else "Specials"
        )
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: Video, position):
        if item.season != self.season and self.season >= 0:
            return
        # cm = []
        list_item = item.build_list_item()

        url_params = build_url(
            {
                "mode": "playback.media",
                "id": self.series.id,
                "episode": position,
                "media_type": "series",
            }
        )

        return url_params, list_item, False
