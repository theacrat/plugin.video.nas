import sys
from dataclasses import dataclass, field
from typing import Callable

from xbmcgui import Dialog
from xbmcplugin import setContent, endOfDirectory, addDirectoryItem, setPluginCategory

from addon import nas_addon
from apis.StremioAPI import stremio_api
from indexers.base_indexer import NASListItem
from modules.kodi_utils import (
    get_property,
    container_refresh_input,
    is_home,
    build_url,
    log,
)
from modules.library import get_continue_watching


def add(
    url_params,
    list_name,
    iconImage="folder",
    original_image=False,
    cm_items=None,
):
    if cm_items is None:
        cm_items = []
    is_folder = url_params.get("isFolder", "true") == "true"
    url = build_url(url_params)
    list_item = NASListItem()
    list_item.setLabel(list_name)
    list_item.setArt(
        {
            # "icon": icon,
            # "poster": icon,
            # "thumb": icon,
            "fanart": nas_addon.fanart,
            # "banner": icon,
            # "landscape": icon,
        }
    )
    info_tag = list_item.getVideoInfoTag()
    info_tag.setPlot(" ")
    if cm_items and not is_home():
        list_item.addContextMenuItems(cm_items)
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
            self.settings,
        ]

        for count, item in enumerate(root_list):
            name: str = item.__name__
            add({"mode": "navigator", "func": name}, name.title(), name, False)
        self.end_directory()

    def home(self):
        from indexers.catalog import CatalogType

        if len(get_continue_watching()):
            add(
                {
                    "mode": "build",
                    "func": "catalog",
                    "catalog_type": CatalogType.CONTINUE.value,
                },
                "Continue watching",
            )
        for i, c in enumerate(stremio_api.get_home_catalogs()):
            add(
                {
                    "mode": "build",
                    "func": "catalog",
                    "catalog_type": CatalogType.HOME.value,
                    "idx": i,
                },
                c.title,
            )
        self.end_directory()

    def discover(self):
        for t in stremio_api.get_discover_types():
            add({"mode": "build", "func": "discover", "discover_type": t}, t.title())
        self.end_directory()

    def library(self):
        from indexers.catalog import CatalogType

        for i, t in enumerate(stremio_api.get_library_types()):
            add(
                {
                    "mode": "build",
                    "func": "catalog",
                    "catalog_type": CatalogType.LIBRARY,
                    "library_filter": t if i else None,
                },
                t.title(),
            )
        self.end_directory()

    def search(self):
        from indexers.catalog import CatalogType

        stremio_api.get_data_store()
        query = Dialog().input("Search Query")

        if not query:
            return self.end_directory(False)

        for i, c in enumerate(stremio_api.get_search_catalogs()):
            add(
                {
                    "mode": "build",
                    "func": "catalog",
                    "catalog_type": CatalogType.SEARCH.value,
                    "idx": i,
                    "search": query,
                },
                c.title,
            )
        self.end_directory()

    def settings(self):
        self.end_directory()

    def end_directory(self, succeeded=True):
        handle = int(sys.argv[1])
        setContent(handle, "files")
        setPluginCategory(handle, self.name)
        endOfDirectory(handle, succeeded)
