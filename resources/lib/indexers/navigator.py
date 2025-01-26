import sys
from dataclasses import dataclass, field
from typing import Callable

from xbmcgui import Dialog
from xbmcplugin import setContent, endOfDirectory, addDirectoryItem, setPluginCategory

from apis.StremioAPI import stremio_api
from indexers.base_indexer import NASListItem
from indexers.catalog import CatalogType
from modules.utils import (
    build_url,
    KodiDirectoryType,
)


def add(
    url_params,
    list_name,
    is_folder=True,
):
    url = build_url(url_params)
    list_item = NASListItem()
    list_item.setLabel(list_name)
    addDirectoryItem(int(sys.argv[1]), url, list_item, is_folder)


@dataclass
class Navigator:
    name: str = field(default="NAS")
    view_type: str = field(default_factory=str)
    content: str = field(default_factory=str)

    def main(self):
        root_list: list[Callable[[], None]] = [
            self.home,
            self.discover,
            self.library,
            self.search,
        ]

        for count, item in enumerate(root_list):
            name: str = item.__name__
            add({"mode": "navigator", "func": name}, name.title())
        self.end_directory()

    def home(self):
        add(
            {
                "mode": "indexer",
                "func": "catalog",
                "catalog_type": CatalogType.CONTINUE,
            },
            "Continue watching",
        )
        for i, c in enumerate(stremio_api.home_catalogs):
            add(
                {
                    "mode": "indexer",
                    "func": "catalog",
                    "catalog_type": CatalogType.HOME,
                    "idx": i,
                },
                c.title,
            )
        self.end_directory()

    def discover(self):
        for t in stremio_api.get_discover_types():
            add({"mode": "indexer", "func": "discover", "content_type": t}, t.title())
        self.end_directory()

    def library(self):
        for i, t in enumerate(stremio_api.get_library_types()):
            add(
                {
                    "mode": "indexer",
                    "func": "catalog",
                    "catalog_type": CatalogType.LIBRARY,
                    "library_filter": t if i else None,
                },
                t.title(),
            )
        self.end_directory()

    def search(self):
        stremio_api.get_data_store()
        query = Dialog().input("Search Query")

        if not query:
            return self.end_directory(False)

        for i, c in enumerate(stremio_api.search_catalogs):
            add(
                {
                    "mode": "indexer",
                    "func": "catalog",
                    "catalog_type": CatalogType.SEARCH,
                    "idx": i,
                    "search": query,
                },
                c.title,
            )
        self.end_directory()

    def end_directory(self, succeeded=True):
        handle = int(sys.argv[1])
        setContent(handle, KodiDirectoryType.FILES)
        setPluginCategory(handle, self.name)
        endOfDirectory(handle, succeeded)
