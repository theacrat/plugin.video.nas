from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import IntEnum, auto
from threading import Thread
from typing import Callable

from xbmcplugin import endOfDirectory

from apis.StremioAPI import stremio_api
from classes.StremioMeta import StremioMeta
from classes.StremioStream import StremioStream
from modules.kodi_utils import (
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
    id: str
    media_type: str
    episode: int | None = None
    play_type: PlayTypes | None = PlayTypes.DEFAULT
    pre_scrape: bool | None = True
    background: bool | None = False
    meta: StremioMeta = field(init=False)
    results: list[list[StremioStream]] = field(init=False, default_factory=list)
    result_listeners: list[Callable[[int], None]] = field(
        init=False, default_factory=list
    )
    progress_thread: Thread = field(init=False, default=None)
    resolve_dialog_made: bool = field(init=False, default=False)

    def __post_init__(self):
        self.meta = stremio_api.get_metadata_by_id(self.id, self.media_type)

    def play(self):
        hide_busy_dialog()

        return self.get_sources()

    def get_sources(self):
        self.progress_thread = Thread(
            target=stremio_api.get_streams_by_id,
            kwargs={
                "id": (
                    self.meta.videos[self.episode].id
                    if self.media_type == "series"
                    else self.meta.behaviorHints.defaultVideoId or self.meta.id
                ),
                "media_type": self.media_type,
                "results": self.results,
                "callback": self.process_results,
            },
        )

        self.progress_thread.start()

        return self.display_results()

    def process_results(self, results: list[StremioStream], position):
        self.results[position] = [r for r in results if r.url]
        for l in self.result_listeners:
            l(position)

    def display_results(self):
        results_window = SourcesResults(
            results=self.results,
            result_listeners=self.result_listeners,
            meta=self.meta,
            episode=self.episode,
            pre_scrape=self.pre_scrape,
        )

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
            playback_percent = 0.0
            NASPlayer().run(
                source.url,
                playback_percent,
                meta=self.meta,
                episode=self.episode,
            )
        except Exception as e:
            log(f"Error playing file: {e}")
