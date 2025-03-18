from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntEnum, auto

from classes.StremioAddon import Catalog, ExtraType
from classes.StremioMeta import StremioMeta, StremioType
from indexers.base_indexer import BaseIndexer, NASListItem
from modules.utils import KodiDirectoryType, build_url, run_plugin
from xbmc import InfoTagVideo
from xbmcplugin import addDirectoryItems, endOfDirectory, setContent, setPluginCategory


class CatalogType(IntEnum):
    CONTINUE = auto()
    HOME = auto()
    DISCOVER = auto()
    LIBRARY = auto()
    SEARCH = auto()


@dataclass
class Catalog(BaseIndexer[StremioMeta]):
    catalog_type: CatalogType
    idx: int | None = -1
    content_type: str | None = None
    search: str | None = None
    genre: str | None = None
    library_filter: str | None = None

    def __post_init__(self):
        handle = int(sys.argv[1])

        name: str | None = None
        data: list[StremioMeta] | None = None
        catalog: Catalog | None = None

        from apis.StremioAPI import stremio_api

        match self.catalog_type:
            case CatalogType.CONTINUE:
                from modules.library import get_continue_watching

                data = get_continue_watching()
                name = "Continue watching"
            case CatalogType.HOME:
                catalog = (
                    c[self.idx]
                    if len(c := stremio_api.home_catalogs) > self.idx
                    else None
                )
            case CatalogType.DISCOVER:
                catalog = (
                    c[self.idx]
                    if len(
                        c := stremio_api.get_discover_catalogs_by_type(
                            self.content_type
                        )
                    )
                    > self.idx
                    else None
                )
            case CatalogType.LIBRARY:
                data = stremio_api.get_library(self.library_filter)
                name = f"Library - {self.library_filter or 'All'}"
            case CatalogType.SEARCH:
                catalog = (
                    c[self.idx]
                    if len(c := stremio_api.search_catalogs) > self.idx
                    else None
                )

        if not data and catalog:
            extra_type, extra_query = (
                [ExtraType.SEARCH, self.search]
                if self.search
                else [ExtraType.DISCOVER, self.genre] if self.genre else [None, None]
            )
            data = stremio_api.get_catalog(catalog, extra_type, extra_query)
            name = catalog.title

        if not data:
            data = []

        addDirectoryItems(handle, self._worker(data))
        setContent(handle, KodiDirectoryType.TVSHOWS)
        setPluginCategory(handle, name)
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(
        self, item: StremioMeta, position: int
    ) -> tuple[str, NASListItem, bool]:
        list_item = item.build_list_item(self.catalog_type == CatalogType.CONTINUE)
        context_menu = []

        if self.catalog_type == CatalogType.CONTINUE:
            if item.library.state.video_id:
                tag: InfoTagVideo = list_item.getVideoInfoTag()
                tag.setResumePoint(
                    item.library.state.timeOffset, item.library.state.duration
                )
                context_menu.append(
                    (
                        "Dismiss",
                        run_plugin(
                            {
                                "mode": "library",
                                "func": "clear_progress",
                                "content_id": item.id,
                                "content_type": item.type,
                            },
                            build_only=True,
                        ),
                    ),
                )
            else:
                context_menu.append(
                    (
                        "Dismiss",
                        run_plugin(
                            {
                                "mode": "library",
                                "func": "dismiss_notification",
                                "content_id": item.id,
                                "content_type": item.type,
                            },
                            build_only=True,
                        ),
                    ),
                )
        list_item.addContextMenuItems(context_menu)
        url_params = (
            build_url(
                {
                    "mode": "playback",
                    "func": "media",
                    "content_id": item.id,
                    "content_type": item.type,
                }
            )
            if item.type == StremioType.MOVIE
            else build_url(
                {
                    "mode": "indexer",
                    "func": "seasons",
                    "content_id": item.id,
                    "content_type": item.type,
                }
                if not self.catalog_type == CatalogType.CONTINUE
                or not item.library.state.video_id
                else {
                    "mode": "playback",
                    "func": "media",
                    "content_id": item.id,
                    "content_type": item.type,
                    "episode_id": item.library.state.video_id,
                }
            )
        )
        return (
            url_params,
            list_item,
            not (
                self.catalog_type == CatalogType.CONTINUE
                and item.library.state.video_id
            )
            and item.type != StremioType.MOVIE,
        )
