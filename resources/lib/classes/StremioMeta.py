from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from functools import cached_property
from typing import Any

import xbmc

from classes.StremioStream import StremioStream
from classes.base_class import StremioObject
from indexers.base_indexer import NASListItem
from modules.utils import (
    log,
    run_plugin,
    update_container,
    KodiContentType,
)


class PosterShape(StrEnum):
    SQUARE = auto()
    LANDSCAPE = auto()
    POSTER = auto()


class StremioType(StrEnum):
    MOVIE = auto()
    SERIES = auto()
    CHANNEL = auto()
    TV = auto()
    OTHER = auto()

    @classmethod
    def get_sort_key(cls, content_type: str) -> int:
        enum: cls
        try:
            enum = cls(content_type)
        except ValueError:
            enum = cls.OTHER
        return list(cls).index(enum)


@dataclass
class Trailer(StremioObject):
    source: str
    type: str


@dataclass
class Link(StremioObject):
    name: str
    category: str
    url: str


@dataclass
class BehaviorHints(StremioObject):
    defaultVideoId: str | None = field(default=None)


@dataclass
class Video(StremioObject):
    id: str
    title: str
    released: datetime
    thumbnail: str | None = field(default=None)
    streams: list[StremioStream] = field(default_factory=list)
    available: bool | None = field(default=None)
    episode: int | None = field(default=None)
    season: int | None = field(default=None)
    trailers: list[StremioStream] = field(default_factory=list)
    overview: str | None = field(default=None)

    parent: StremioMeta = field(init=False, repr=False, compare=False)

    @classmethod
    def transform_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        if "name" in data and "title" not in data:
            data["title"] = data["name"]
        if "stream" in data:
            data["streams"] = [data["stream"]]
        if "firstAired" in data:
            data["released"] = data["firstAired"]
        return super().transform_dict(data)

    @property
    def watched(self):
        try:
            return self.parent.library.state.watched_bitfield.get_video(self.id)
        except:
            from xbmc import LOGDEBUG

            log("Couldn't access watched bitfield value, returning False", LOGDEBUG)
            return False

    @cached_property
    def idx(self) -> int:
        return self.parent.videos.index(self)

    @cached_property
    def next_episode(self) -> Video | None:
        return (
            self.parent.videos[self.idx + 1] if self.parent.videos[-1] != self else None
        )

    def build_list_item(self) -> NASListItem:
        list_item = self.parent.build_list_item(True)

        list_item.setLabel(self.title)
        if self.thumbnail:
            list_item.setArt({"fanart": self.thumbnail})

        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setTitle(self.title)
        info_tag.setMediaType(KodiContentType.EPISODE)
        info_tag.setPlaycount(1 if self.watched else 0),
        info_tag.setPlot(self.overview)
        info_tag.setPremiered(self.released.isoformat())
        info_tag.setFirstAired(self.released.isoformat())
        info_tag.setTvShowTitle(self.parent.name)
        if self.season and self.episode:
            info_tag.setSeason(self.season)
            info_tag.setEpisode(self.episode)
        info_tag.setUniqueID(self.id, "stremio_video")

        progress_state = self.parent.library.state
        if progress_state.video_id == self.id:
            info_tag.setResumePoint(progress_state.timeOffset, progress_state.duration)

        cm_items: list[tuple[str, str]] = [
            (
                f"Mark as {'Unwatched' if self.watched else 'Watched'}",
                run_plugin(
                    {
                        "mode": "library",
                        "func": "watched_status",
                        "content_id": self.parent.id,
                        "content_type": self.parent.type,
                        "video_id": self.id,
                        "status": not self.watched,
                    },
                    build_only=True,
                ),
            )
        ]
        list_item.addContextMenuItems(cm_items)

        return list_item


@dataclass
class StremioMeta(StremioObject):
    from classes.StremioLibrary import StremioLibrary

    id: str
    type: str
    name: str
    genres: list[str] = field(default_factory=list)
    poster: str | None = field(default=None)
    posterShape: str = field(default=PosterShape.POSTER)
    background: str | None = field(default=None)
    logo: str | None = field(default=None)
    description: str | None = field(default=None)
    releaseInfo: str | None = field(default=None)
    director: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    imdbRating: str | None = field(default=None)
    released: datetime | None = field(default=None)
    trailers: list[Trailer] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    videos: list[Video] = field(default_factory=list)
    runtime: str | None = field(default=None)
    language: str | None = field(default=None)
    country: str | None = field(default=None)
    awards: str | None = field(default=None)
    website: str | None = field(default=None)
    behaviorHints: BehaviorHints = field(default_factory=BehaviorHints)

    library: StremioLibrary = field(init=False, repr=False, compare=False)

    @cached_property
    def runtime_seconds(self) -> int:
        if not self.runtime:
            return 0

        import re

        rt = re.sub(
            r"([a-z])min|(?<!\w)([a-z])(?!\w)",
            "",
            str(self.runtime).lower().replace(" ", ""),
        )
        seconds = 0
        if "h" in rt:
            h, rt = rt.split("h")
            seconds += int(h) * 3600
        return seconds + int(rt.replace("mins", "").replace("min", "")) * 60

    @cached_property
    def first_year(self):
        if not self.releaseInfo:
            return 0
        match = re.search(r"\b\d+\b", self.releaseInfo)
        return int(match.group()) if match else 0

    @cached_property
    def seasons(self) -> list[int]:
        return sorted(list({v.season for v in self.videos}), key=lambda k: (k == 0, k))

    @cached_property
    def relations(self) -> list[Link]:
        return [l for l in self.links if l.url.startswith("stremio:///detail")]

    @property
    def watched(self) -> bool:
        if self.type == StremioType.SERIES:
            return (
                not any(not i.watched for i in self.videos if i.season != 0)
                and self.videos
            )
        else:
            return self.library.state.timesWatched > 0

    @cached_property
    def kodi_type(self) -> str:
        match self.type:
            case StremioType.SERIES:
                return KodiContentType.TVSHOW
            case StremioType.MOVIE:
                return KodiContentType.MOVIE
            case _:
                return KodiContentType.VIDEO

    def _consolidate_links(self, link_category: str, legacy_field: list[str]):
        try:
            if not legacy_field:
                return
            self.links.extend(
                Link(li, link_category, "")
                for li in legacy_field
                if not any(
                    i.name == li and i.category == link_category for i in self.links
                )
            )
        except TypeError:
            from xbmc import LOGERROR

            log(f"Failed to consolidate: {link_category} from {legacy_field}", LOGERROR)

    def __post_init__(self):
        legacy_fields = [
            ("Genres", self.genres),
            ("Cast", self.cast),
            ("Directors", self.director),
        ]

        for category, legacy_field in legacy_fields:
            self._consolidate_links(category, legacy_field)

        from apis.StremioAPI import stremio_api

        self.library = stremio_api.get_data_by_meta(self)

        if self.videos:
            self.videos.sort(
                key=lambda e: (
                    e.season,
                    e.episode,
                    e.released,
                )
            )

            self.library.state.create_bitfield([v.id for v in self.videos])

        for video in self.videos:
            video.parent = self

    def get_links_by_category(self, category: str):
        return [l.name for l in self.links if l.category == category]

    def build_list_item(self, base_only=False) -> NASListItem:
        list_item = NASListItem()

        list_item.setLabel(self.name)
        list_item.setArt(
            {
                "poster": self.poster,
                "fanart": self.background,
                "icon": self.poster,
                "clearlogo": self.logo,
                "tvshow.poster": self.poster,
                "tvshow.clearlogo": self.logo,
            }
        )

        if (
            not base_only
            and self.videos
            and (bitfield := self.library.state.watched_bitfield)
        ):
            episodes = [v for v in self.videos if v.season != 0]
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
        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setMediaType(self.kodi_type)
        info_tag.setTitle(self.name)
        info_tag.setPlaycount(1 if self.watched else 0),
        info_tag.setPlot(self.description)
        info_tag.setYear(int(self.first_year))
        info_tag.setDuration(self.runtime_seconds)
        info_tag.setCountries([self.country])
        if self.released:
            info_tag.setPremiered(self.released.isoformat())
            info_tag.setFirstAired(self.released.isoformat())
        info_tag.setGenres(self.get_links_by_category("Genre"))
        info_tag.setWriters(self.get_links_by_category("Writers"))
        info_tag.setDirectors(self.get_links_by_category("Directors"))
        info_tag.setRating(float(self.imdbRating or 0))
        info_tag.setUniqueIDs(
            {
                "stremio": self.id,
                "stremio_video": self.id,
            }
        )
        info_tag.setCast(
            [
                xbmc.Actor(
                    name=item,
                )
                for item in self.get_links_by_category("Cast")
            ]
        )

        cm_items: list[tuple[str, str]] = []

        if not self.videos:
            cm_items.append(
                (
                    f"Mark as {'Unwatched' if self.watched else 'Watched'}",
                    run_plugin(
                        {
                            "mode": "library",
                            "func": "watched_status",
                            "content_id": self.id,
                            "content_type": self.type,
                            "status": not self.watched,
                        },
                        build_only=True,
                    ),
                ),
            )
        if not base_only:
            is_in_library = not (self.library.temp or self.library.removed)
            cm_items.append(
                (
                    f"{'Remove from' if is_in_library else 'Add to'} Library",
                    run_plugin(
                        {
                            "mode": "library",
                            "func": "status",
                            "content_id": self.id,
                            "content_type": self.type,
                            "status": not is_in_library,
                        },
                        build_only=True,
                    ),
                )
            )

            cm_items.append(
                (
                    "View relations",
                    update_container(
                        {
                            "mode": "indexer",
                            "func": "relations",
                            "content_id": self.id,
                            "content_type": self.type,
                        },
                        build_only=True,
                    ),
                )
            )

        list_item.addContextMenuItems(cm_items)

        progress_state = self.library.state
        if progress_state.video_id == self.id:
            info_tag.setResumePoint(progress_state.timeOffset, progress_state.duration)

        return list_item
