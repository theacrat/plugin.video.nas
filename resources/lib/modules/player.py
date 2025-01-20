from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Thread

import xbmc
from xbmc import InfoTagVideo
from xbmcgui import ListItem

from classes.StremioMeta import StremioMeta
from modules.kodi_utils import (
    hide_busy_dialog,
    close_all_dialog,
    notification,
    log,
    run_plugin,
)


@dataclass
class NASPlayerState:
    stremio_id: str
    stremio_video_id: str
    stremio_type: str
    total_time: float
    last_time: float = field(default=0, init=False)
    last_updated: datetime = field(default=None, init=False)
    playback_speed: int = field(default=1, init=False)
    paused: bool = field(default=False, init=False)
    stopped: bool = field(default=False, init=False)


def run_error():
    notification("Playback failed")


def kill_dialog():
    close_all_dialog()


def make_listing(url, resume_point, meta: StremioMeta, episode: int | None):
    list_item: ListItem
    list_item = (
        meta.videos[episode].build_list_item() if episode else meta.build_list_item()
    )
    info_tag = list_item.getVideoInfoTag()
    info_tag.setFilenameAndPath(url)

    list_item.setPath(url)
    list_item.setProperty("IsPlayable", "true")
    list_item.setProperty("StartPercent", str(resume_point))
    return list_item


def playback_close_dialogs():
    kill_dialog()
    close_all_dialog()


@dataclass
class NASPlayer(xbmc.Player):
    state: NASPlayerState | None = field(init=False, default=None)

    def run(
        self,
        url,
        resume_point,
        meta: StremioMeta,
        episode: int | None,
    ):
        hide_busy_dialog()
        try:
            self.play(url, make_listing(url, resume_point, meta, episode))
        except Exception as e:
            log(str(e))
            run_error()

    def on_stopping(self):
        hide_busy_dialog()
        self.state = None

    def update_library_progress(
        self,
        override_time: int | None = None,
        stopped=False,
        finished=False,
    ):

        if not self.state or self.state.stopped:
            return

        start_stop = not self.state.last_updated or stopped or finished

        curr_time: float
        now = datetime.now()
        if stopped:
            curr_time = (
                (now - self.state.last_updated).total_seconds()
                * self.state.playback_speed
            ) + self.state.last_time
            curr_time = min(curr_time, self.state.total_time)
            self.state.stopped = True
        elif finished:
            curr_time = self.state.total_time
            self.state.stopped = True
        else:
            curr_time = override_time if override_time else self.getTime()
            self.state.last_updated = now
        curr_time = max(curr_time, 0)
        self.state.last_time = curr_time

        update_args = {
            "mode": "library",
            "func": "player_update",
            "content_id": self.state.stremio_id,
            "video_id": self.state.stremio_video_id,
            "content_type": self.state.stremio_type,
            "curr_time": round(curr_time * 1000),
            "total_time": round(self.state.total_time * 1000),
            "playing": not self.state.paused and not self.state.stopped,
            "start_stop": start_stop,
        }

        Thread(
            target=run_plugin,
            args=(update_args, False),
        ).start()

    def onAVStarted(self):
        hide_busy_dialog()
        item: ListItem = self.getPlayingItem()
        video_tag: InfoTagVideo = item.getVideoInfoTag()
        stremio_id = video_tag.getUniqueID("stremio")
        stremio_video_id = video_tag.getUniqueID("stremio_video")

        if not stremio_id:
            self.state = None
            return

        stremio_type = "video"
        match video_tag.getMediaType():
            case "episode":
                stremio_type = "series"
            case "movie":
                stremio_type = "movie"

        self.state = NASPlayerState(
            stremio_id, stremio_video_id, stremio_type, self.getTotalTime()
        )

        self.update_library_progress()

    def onPlayBackSeek(self, time: int, seekOffset: int) -> None:
        self.update_library_progress(override_time=round(time / 1000))

    def onPlayBackSeekChapter(self, chapter: int) -> None:
        self.update_library_progress()

    def onPlayBackSpeedChanged(self, speed: int) -> None:
        self.update_library_progress()
        if self.state:
            self.state.playback_speed = speed

    def onPlayBackPaused(self) -> None:
        if self.state:
            self.state.paused = True
        self.update_library_progress()

    def onPlayBackResumed(self) -> None:
        if self.state:
            self.state.paused = False

    def onPlayBackStopped(self) -> None:
        self.update_library_progress(stopped=True)
        self.on_stopping()

    def onPlayBackEnded(self) -> None:
        self.update_library_progress(finished=True)
        self.on_stopping()

    def onPlayBackError(self) -> None:
        self.update_library_progress(stopped=True)
        self.on_stopping()
