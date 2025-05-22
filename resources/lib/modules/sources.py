from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import IntEnum, auto
from threading import Thread
from typing import Callable

from xbmcplugin import endOfDirectory

from apis.StremioAPI import stremio_api
from modules.utils import (
    hide_busy_dialog,
    log,
)
from modules.player import NASPlayer
from windows.sources import SourcesResults


class PlayTypes(IntEnum):
    DEFAULT = auto()
    AUTOSCRAPE = auto()
    AUTOPLAY = auto()


@dataclass
class Sources:
    from classes.StremioMeta import StremioMeta
    from classes.StremioStream import StremioStream

    content_id: str
    content_type: str
    episode: int | None = None
    episode_id: str | None = None
    play_type: PlayTypes | None = PlayTypes.DEFAULT
    meta: StremioMeta = field(init=False)
    results: list[list[StremioStream] | None] | None = field(init=False, default=None)
    resume: bool = field(default=False)
    result_listeners: list[
        Callable[[list[list[StremioStream] | None] | None, int], None]
    ] = field(init=False, default_factory=list)

    def __post_init__(self):
        self.meta = stremio_api.get_metadata_by_id(self.content_id, self.content_type)

        if self.episode_id:
            self.episode = next(
                idx for idx, i in enumerate(self.meta.videos) if i.id == self.episode_id
            )

    def play(self):
        return self.get_sources()

    def get_sources(self):
        Thread(
            target=stremio_api.get_streams_by_id,
            kwargs={
                "content_id": (
                    self.meta.videos[self.episode].id
                    if self.episode is not None
                    else self.meta.behaviorHints.defaultVideoId or self.meta.id
                ),
                "content_type": self.content_type,
                "callback": self.process_results,
            },
        ).start()

        return self.display_results()

    def process_results(self, results: list[StremioStream], position, addon_count: int):
        if not self.results:
            self.results = [None for _ in range(addon_count)]
        self.results[position] = [r for r in results if r.url]
        for l in self.result_listeners:
            l(self.results, position)

    def display_results(self):
        results_window = SourcesResults(
            results=self.results,
            result_listeners=self.result_listeners,
            meta=self.meta,
            episode=self.episode,
        )

        from classes.StremioStream import StremioStream

        selection: StremioStream | None = results_window.run()

        if selection:
            return self.play_file(self.results, selection)
        else:
            handle = int(sys.argv[1])
            return endOfDirectory(handle, False)

    def play_file(self, results, source: StremioStream):
        try:
            hide_busy_dialog()
            if not source:
                source = results[0]
            hide_busy_dialog()
            NASPlayer().run(
                source.url,
                (self.meta.library.state.timeOffset or 0) if self.resume else 0,
                meta=self.meta,
                episode=self.episode,
            )
        except Exception as e:
            log(f"Error playing file: {e}")
