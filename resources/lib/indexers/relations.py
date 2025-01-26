import sys
from dataclasses import dataclass

from xbmcgui import ListItem
from xbmcplugin import addDirectoryItems, setContent, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioMeta import Link, StremioType
from indexers.base_indexer import BaseIndexer, NASListItem
from modules.utils import build_url, log, KodiDirectoryType


@dataclass
class Relations(BaseIndexer[Link]):
    content_id: str
    content_type: str

    def __post_init__(self):
        handle = int(sys.argv[1])

        series = stremio_api.get_metadata_by_id(self.content_id, self.content_type)
        log(series.relations)
        addDirectoryItems(handle, self._worker(series.relations))
        setContent(handle, KodiDirectoryType.SETS)
        setPluginCategory(handle, series.name)
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: Link, position: int) -> tuple[str, ListItem, bool]:
        list_item = NASListItem()
        list_item.setLabel(item.name)
        segments = item.url.split("/")
        url_params = (
            build_url(
                {
                    "mode": "playback",
                    "func": "media",
                    "content_id": segments[-1],
                    "content_type": StremioType.MOVIE,
                }
            )
            if segments[-2] == StremioType.MOVIE
            else build_url(
                {
                    "mode": "indexer",
                    "func": "seasons",
                    "content_id": segments[-1],
                }
            )
        )
        return url_params, list_item, True
