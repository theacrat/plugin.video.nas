import sys
from dataclasses import dataclass, field

from xbmcplugin import addDirectoryItems, setContent, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioMeta import StremioMeta, StremioType
from indexers.base_indexer import BaseIndexer, NASListItem
from modules.utils import build_url, KodiDirectoryType


@dataclass
class Seasons(BaseIndexer[int]):
    content_id: str
    content_type: str
    series: StremioMeta = field(init=False)

    def __post_init__(self):
        handle = int(sys.argv[1])

        self.series = stremio_api.get_metadata_by_id(self.content_id, self.content_type)

        data = self.series.seasons
        if len(data) == 1:
            from indexers.episodes import Episodes

            return Episodes(
                content_id=self.content_id,
                content_type=self.content_type,
                refreshed=self.refreshed,
                season=data[0],
            )

        addDirectoryItems(handle, self._worker(data))
        setContent(handle, KodiDirectoryType.SEASONS)
        setPluginCategory(handle, self.series.name)
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: int, position: int):
        list_item = NASListItem()
        list_item.setLabel(f"Season {item}" if item != 0 else "Specials")
        info_tag = list_item.getVideoInfoTag()
        info_tag.setPlaycount(
            0
            if any(v.season == item and not v.watched for v in self.series.videos)
            else 1
        )
        url_params = build_url(
            {
                "mode": "indexer",
                "func": "episodes",
                "content_id": self.content_id,
                "content_type": self.content_type,
                "season": item,
            }
        )
        return url_params, list_item, True
