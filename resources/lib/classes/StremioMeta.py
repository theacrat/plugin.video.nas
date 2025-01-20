from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Optional, Union, get_type_hints

import xbmc

from indexers.base_indexer import NASListItem
from modules.kodi_utils import log, build_url, run_plugin


@dataclass
class Trailer:
    source: str
    type: str | None = None


@dataclass
class TrailerStream:
    title: str
    ytId: str


@dataclass
class Link:
    name: str
    category: str
    url: str | None = None


@dataclass
class BehaviorHints:
    defaultVideoId: str | None = None
    hasScheduledVideos: bool | None = None


@dataclass
class Popularities:
    trakt: float | None = None
    stremio: float | None = None
    stremio_lib: float | None = None
    moviedb: float | None = None


@dataclass
class Video:
    id: str
    title: str | None = ""
    name: str | None = ""
    released: str | None = ""
    number: int | None = None
    firstAired: str | None = None
    tvdb_id: int | None = None
    rating: str | None = None
    overview: str | None = None
    thumbnail: str | None = None
    episode: int | None = None
    description: str | None = None
    season: int | None = None
    parent: StremioMeta = field(init=False, repr=False, compare=False, default=None)

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
        list_item = self.parent.build_list_item()

        list_item.setLabel(self.name)
        if self.thumbnail:
            list_item.setArt({"fanart": self.thumbnail})

        info_tag: xbmc.InfoTagVideo = list_item.getVideoInfoTag()
        info_tag.setTitle(self.name)
        info_tag.setMediaType("episode")
        info_tag.setPlaycount(1 if self.watched else 0),
        info_tag.setPlot(self.description)
        info_tag.setTvShowTitle(self.parent.name)
        # info_tag.setTvShowStatus(self.parent.status)
        info_tag.setSeason(self.season)
        info_tag.setEpisode(self.episode)
        info_tag.setUniqueID(self.id, "stremio_video")

        progress_state = self.parent.library.state
        if progress_state.video_id == self.id:
            info_tag.setResumePoint(progress_state.timeOffset, progress_state.duration)
        if self.firstAired:
            info_tag.setPremiered(self.firstAired)
            info_tag.setFirstAired(self.firstAired)

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

    def __post_init__(self):
        self.name = self.title or self.name
        self.description = self.description or self.overview


@dataclass
class StremioMeta:
    from classes.StremioLibrary import StremioLibrary

    id: str
    type: str
    name: str
    imdb_id: str | None = ""
    kitsu_id: str | None = ""
    poster: str | None = ""
    background: str | None = ""
    logo: str | None = ""
    description: str | None = ""
    releaseInfo: str | None = ""
    year: str | None = None
    runtime: str | None = None
    status: str | None = ""
    animeType: str | None = ""
    slug: str | None = ""
    country: str | None = ""
    awards: str | None = ""
    dvdRelease: str | None = ""
    imdbRating: str | None = ""
    moviedb_id: int | None = 0
    tvdb_id: int | None = 0
    popularities: Popularities | None = None
    popularity: float | None = 0
    released: str | None = ""
    trailers: list[Trailer] = field(default_factory=list)
    trailerStreams: list[TrailerStream] = field(default_factory=list)
    videos: list[Video] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    genre: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    director: list[str] = field(default_factory=list)
    writer: list[str] = field(default_factory=list)
    behaviorHints: BehaviorHints = field(default_factory=BehaviorHints)
    library: StremioLibrary = field(init=False, repr=False, compare=False, default=None)

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
        if not self.year:
            return 0
        match = re.search(r"\b\d+\b", self.year)
        return int(match.group()) if match else 0

    @cached_property
    def seasons(self) -> list[int]:
        return sorted(list({v.season for v in self.videos}), key=lambda k: (k == 0, k))

    @property
    def watched(self) -> bool:
        if self.type == "series":
            return (
                not any(not i.watched for i in self.videos if i.season != 0)
                and self.videos
            )
        else:
            return self.library.state.timesWatched > 0

    @cached_property
    def kodi_type(self) -> str:
        match self.type:
            case "series":
                return "tvshow"
            case "movie":
                return "movie"
            case _:
                return "video"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StremioMeta:
        return json.loads(json.dumps(data), object_hook=object_hook)

    @classmethod
    def from_list(cls, data: list[dict[str, Any]]) -> list[StremioMeta]:
        return [StremioMeta.from_dict(a) for a in data]

    def _consolidate_links(self, link_category: str, legacy_field: list[str]):
        try:
            if not legacy_field:
                return
            self.links.extend(
                Link(li, link_category)
                for li in legacy_field
                if not any(
                    i.name == li and i.category == link_category for i in self.links
                )
            )
        except:
            from xbmc import LOGERROR

            log(f"Failed to consolidate: {link_category} from {legacy_field}", LOGERROR)

    def __post_init__(self):
        if self.genre and not self.genres:
            self.genres = self.genre
            self.genre = None

        legacy_fields = [
            ("Genres", self.genres),
            ("Cast", self.cast),
            ("Writers", self.writer),
            ("Directors", self.director),
        ]

        for category, field in legacy_fields:
            self._consolidate_links(category, field)

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

    def build_list_item(self) -> NASListItem:
        list_item = NASListItem()

        list_item.setLabel(self.name)
        # list_item.addContextMenuItems(cm)
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

        if self.videos and (bitfield := self.library.state.watched_bitfield):
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
        info_tag.setPremiered(self.released)
        info_tag.setFirstAired(self.released)
        info_tag.setIMDBNumber(self.imdb_id)
        info_tag.setGenres(self.get_links_by_category("Genre"))
        info_tag.setWriters(self.get_links_by_category("Writers"))
        info_tag.setDirectors(self.get_links_by_category("Directors"))
        info_tag.setRating(float(self.imdbRating or 0))
        info_tag.setUniqueIDs(
            {
                "stremio": self.id,
                "stremio_video": self.id,
                "imdb": self.imdb_id,
                "tmdb": str(self.moviedb_id),
                "tvdb": str(self.tvdb_id),
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
        list_item.addContextMenuItems(cm_items)

        progress_state = self.library.state
        if progress_state.video_id == self.id:
            info_tag.setResumePoint(progress_state.timeOffset, progress_state.duration)
        # TODO is still airing
        # info_tag.setTvShowStatus(meta_get("status"))

        return list_item


def object_hook(
    d: dict[str, Any]
) -> [
    Trailer
    | TrailerStream
    | Link
    | BehaviorHints
    | Popularities
    | Video
    | StremioMeta
    | None
]:
    def filter_kwargs(cls: type, data: dict[str, Any]) -> dict[str, Any]:
        fields = get_type_hints(cls)
        return {k: v for k, v in data.items() if k in fields}

    if all(k in d for k in ("id", "type")):
        return StremioMeta(**filter_kwargs(StremioMeta, d))
    elif "id" in d:
        return Video(**filter_kwargs(Video, d))
    elif all(k in d for k in ("source",)):
        return Trailer(**filter_kwargs(Trailer, d))
    elif all(k in d for k in ("title", "ytId")):
        return TrailerStream(**filter_kwargs(TrailerStream, d))
    elif all(k in d for k in ("name", "category", "url")):
        return Link(**filter_kwargs(Link, d))
    elif isinstance(d, dict) and any(
        k in d for k in ("defaultVideoId", "hasScheduledVideos")
    ):
        return BehaviorHints(**filter_kwargs(BehaviorHints, d))
    elif isinstance(d, dict) and any(
        k in d for k in ("trakt", "stremio", "stremio_lib", "moviedb")
    ):
        return Popularities(**filter_kwargs(Popularities, d))
    return
