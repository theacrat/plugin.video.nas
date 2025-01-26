import sys
from dataclasses import dataclass

from xbmcplugin import addDirectoryItems, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioAddon import Catalog, ExtraType
from indexers.base_indexer import BaseIndexer, NASListItem
from indexers.catalog import CatalogType
from modules.utils import build_url


@dataclass
class Discover(BaseIndexer[Catalog | str]):
    content_type: str
    idx: int | None = None

    def __post_init__(self):
        handle = int(sys.argv[1])

        data: [Catalog | str]
        title: str
        catalogs = stremio_api.get_discover_catalogs_by_type(self.content_type)
        if self.idx is None:
            data = catalogs
            title = self.content_type
        else:
            catalog = catalogs[self.idx]
            genre_extras = [e for e in catalog.extra if e.name == ExtraType.DISCOVER][0]
            data = genre_extras.options.copy()
            if (
                not genre_extras.isRequired
                and ExtraType.DISCOVER not in catalog.extraRequired
            ):
                data.insert(0, None)
            title = catalogs[self.idx].title

        addDirectoryItems(handle, self._worker(data))
        setPluginCategory(handle, title.capitalize())
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: Catalog | str, idx: int):
        list_item = NASListItem()
        if isinstance(item, Catalog):
            list_item.setLabel(item.title)
            url_params = build_url(
                {
                    "mode": "indexer",
                    "func": "discover",
                    "content_type": self.content_type,
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
                    "content_type": self.content_type,
                    "idx": self.idx,
                    "genre": item,
                }
            )
        return url_params, list_item, True
