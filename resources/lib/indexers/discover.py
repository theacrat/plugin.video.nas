import sys
from dataclasses import dataclass

from xbmcplugin import addDirectoryItems, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioAddon import StremioCatalog
from indexers.base_indexer import BaseIndexer, NASListItem
from indexers.catalog import CatalogType
from modules.kodi_utils import build_url


@dataclass
class Discover(BaseIndexer[StremioCatalog | str]):
    discover_type: str
    idx: int | None = None

    def __post_init__(self):
        handle = int(sys.argv[1])

        data: [StremioCatalog | str]
        title: str
        catalogs = stremio_api.get_discover_catalogs_by_type(self.discover_type)
        if self.idx is None:
            data = catalogs
            title = self.discover_type
        else:
            catalog = catalogs[self.idx]
            genre_extras = [e for e in catalog.extra if e.name == "genre"][0]
            data = genre_extras.options.copy()
            if not genre_extras.isRequired and "genre" not in catalog.extraRequired:
                data.insert(0, None)
            title = catalogs[self.idx].title

        addDirectoryItems(handle, self._worker(data))
        setPluginCategory(handle, title.capitalize())
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: [StremioCatalog | str], idx: int):
        list_item = NASListItem()
        if isinstance(item, StremioCatalog):
            list_item.setLabel(item.title)
            url_params = build_url(
                {
                    "mode": "indexer",
                    "func": "discover",
                    "discover_type": self.discover_type,
                    "idx": idx,
                }
            )
        else:
            list_item.setLabel((item or "Default").capitalize())
            url_params = build_url(
                {
                    "mode": "indexer",
                    "func": "catalog",
                    "catalog_type": CatalogType.DISCOVER,
                    "media_type": self.discover_type,
                    "idx": self.idx,
                    "genre": item,
                }
            )
        return url_params, list_item, True
