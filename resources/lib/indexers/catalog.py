from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntEnum, auto

from xbmc import InfoTagVideo
from xbmcplugin import addDirectoryItems, setContent, setPluginCategory, endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioAddon import StremioCatalog
from classes.StremioMeta import StremioMeta
from indexers.base_indexer import BaseIndexer
from modules.kodi_utils import build_url, log, run_plugin
from modules.library import get_continue_watching


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
    media_type: str | None = None
    search: str | None = None
    genre: str | None = None
    library_filter: str | None = None

    def __post_init__(self):
        handle = int(sys.argv[1])

        name: str | None = None
        data: list[StremioMeta] | None = None
        catalog: StremioCatalog | None = None

        match self.catalog_type:
            case CatalogType.CONTINUE:
                data = get_continue_watching()
                name = "Continue watching"
            case CatalogType.HOME:
                catalog = (
                    c[self.idx]
                    if len(c := stremio_api.get_home_catalogs()) > self.idx
                    else None
                )
            case CatalogType.DISCOVER:
                catalog = (
                    c[self.idx]
                    if len(
                        c := stremio_api.get_discover_catalogs_by_type(self.media_type)
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
                    if len(c := stremio_api.get_search_catalogs()) > self.idx
                    else None
                )

        if not data and catalog:
            data = stremio_api.get_catalog(
                catalog,
                search=f"search={self.search}" if self.search else None,
                genre=f"genre={self.genre}" if self.genre else None,
            )
            name = catalog.title

        addDirectoryItems(handle, self._worker(data))
        setContent(handle, "movies")
        setPluginCategory(handle, name)
        endOfDirectory(handle, cacheToDisc=not self.external)

    def _build_content(self, item: StremioMeta, idx: int):
        list_item = item.build_list_item()
        context_menu = []

        next_episode: int | None = None
        if item.videos:
            episodes = [v for v in item.videos if v.season != 0]
            bitfield = item.library.state.watched_bitfield
            watched_episodes = [v for v in episodes if bitfield.get_video(v.id)]
            list_item.setProperties(
                {
                    "totalepisodes": len(episodes),
                    "totalseasons": len({v.season for v in episodes}),
                    "watchedepisodes": len(watched_episodes),
                    "unwatchedepisodes": len(episodes) - len(watched_episodes),
                    "watchedprogress": (
                        str((len(watched_episodes) / len(episodes)) * 100)
                        if watched_episodes != episodes
                        else 0
                    ),
                }
            )
        if self.catalog_type == CatalogType.CONTINUE:
            if item.videos:
                next_episode = next(
                    (
                        idx
                        for idx, e in enumerate(item.videos)
                        if e.id == item.library.state.video_id
                    ),
                    None,
                )
            if next_episode or item.library.state.video_id == item.id:
                tag: InfoTagVideo = list_item.getVideoInfoTag()
                tag.setResumePoint(
                    item.library.state.timeOffset, item.library.state.duration
                )
                context_menu.append(
                    (
                        "Dismiss",
                        run_plugin(
                            {
                                "mode": "library.clear_progress",
                                "content_id": item.id,
                                "content_type": item.type,
                            },
                            build_only=True,
                        ),
                    ),
                )

            else:
                next_episode = next(
                    (
                        idx
                        for idx, e in enumerate(item.videos)
                        if e.season and not e.watched
                    ),
                    None,
                )
                context_menu.append(
                    (
                        "Dismiss",
                        run_plugin(
                            {
                                "mode": "library.dismiss_notification",
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
                    "mode": "playback.media",
                    "media_type": "movie",
                    "id": item.id,
                }
            )
            if not item.videos
            else build_url(
                {"mode": "build_seasons", "id": item.id}
                if not self.catalog_type == CatalogType.CONTINUE or next_episode is None
                else {
                    "mode": "playback.media",
                    "media_type": "series",
                    "id": item.id,
                    "episode": next_episode,
                }
            )
        )
        return url_params, list_item, bool(item.videos)
