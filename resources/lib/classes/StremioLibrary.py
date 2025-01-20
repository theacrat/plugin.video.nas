from __future__ import annotations

import base64
import json
from functools import cached_property

import math
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, get_type_hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classes.StremioMeta import Video

from modules.kodi_utils import (
    timestamp_zone_format_switcher,
    kodi_refresh,
    run_plugin,
)

STREMIO_WATCHED_COEFFICIENT = 0.7
STREMIO_CREDITS_COEFFICIENT = 0.9


@dataclass
class BitField8:
    n_size: int
    length: int = field(init=False)
    values: bytearray = field(init=False)

    def __post_init__(self):
        n_bytes: int = math.ceil(self.n_size / 8)
        self.length: int = self.n_size
        self.values: bytearray = bytearray(n_bytes)

    @classmethod
    def from_packed(cls: BitField8, compressed, length=None) -> BitField8:
        bf = cls(0)
        bf.values = bytearray(zlib.decompress(compressed))
        bf.length = length if isinstance(length, int) else len(bf.values) * 8
        n_bytes = math.ceil(bf.length / 8)

        if n_bytes > len(bf.values):
            new_values = bytearray(n_bytes)
            for idx, value in enumerate(bf.values):
                new_values[idx] = value
            bf.values = new_values
        return bf

    def get(self, i: int) -> bool:
        index = i // 8
        bit = i % 8
        if index >= len(self.values):
            return False
        return (self.values[index] & (1 << bit)) != 0

    def set(self, i: int, val: bool):
        index = i // 8
        bit = i % 8
        mask = 1 << bit
        if val:
            self.values[index] |= mask
        else:
            self.values[index] &= ~mask

    def last_index_of(self, val: bool) -> int:
        for i in range(self.length - 1, -1, -1):
            if self.get(i) == val:
                return i
        return -1

    def to_packed(self):
        return zlib.compress(self.values)


@dataclass
class WatchedBitfield:
    bitfield: BitField8
    video_ids: list[str]

    @classmethod
    def construct_from_array(
        cls: WatchedBitfield, arr: list[bool], video_ids: list[str]
    ) -> WatchedBitfield:
        bitfield = BitField8(len(video_ids))
        for i, v in enumerate(arr):
            bitfield.set(i, bool(v))
        return cls(bitfield, video_ids)

    @classmethod
    def construct_and_resize(
        cls: WatchedBitfield, serialized: str, video_ids: list[str]
    ) -> WatchedBitfield:
        components = serialized.split(":")
        if len(components) < 3:
            raise ValueError("Invalid components length")

        serialized_buf = components.pop()
        anchor_length = int(components.pop())
        anchor_video_id = ":".join(components)
        anchor_video_idx = (
            video_ids.index(anchor_video_id) if anchor_video_id in video_ids else -1
        )

        offset = (anchor_length - 1) - anchor_video_idx

        anchor_not_found = anchor_video_idx == -1
        must_shift = offset != 0

        if anchor_not_found or must_shift:
            resized_buf = cls(BitField8(len(video_ids)), video_ids)

            if anchor_not_found:
                return resized_buf

            decoded_buf = base64.b64decode(serialized_buf.encode("ascii"))
            prev_buf = BitField8.from_packed(decoded_buf, anchor_length)

            for i in range(len(video_ids)):
                idx_in_prev = i + offset
                if 0 <= idx_in_prev < prev_buf.length:
                    resized_buf.set(i, prev_buf.get(idx_in_prev))
            return resized_buf

        decoded_buf = base64.b64decode(serialized_buf.encode("ascii"))
        buf = BitField8.from_packed(decoded_buf, len(video_ids))
        return cls(buf, video_ids)

    def get(self, idx: int) -> bool:
        return self.bitfield.get(idx)

    def set(self, idx: int, v: bool):
        self.bitfield.set(idx, v)

    def set_video(self, video_id: str, v: bool):
        try:
            idx = self.video_ids.index(video_id)
            self.bitfield.set(idx, v)
        except ValueError:
            pass

    def get_video(self, video_id: str) -> bool:
        try:
            idx = self.video_ids.index(video_id)
            return self.bitfield.get(idx)
        except ValueError:
            return False

    def serialize(self) -> str:
        packed = self.bitfield.to_packed()
        packed_str = base64.b64encode(packed).decode("ascii")
        last_idx = max(0, self.bitfield.last_index_of(True))
        return f"{self.video_ids[last_idx]}:{last_idx + 1}:{packed_str}"


@dataclass
class WatchState:
    lastWatched: str = field(default_factory=str)
    timeWatched: int = field(default=0)
    timeOffset: int = field(default=0)
    overallTimeWatched: int = field(default=0)
    timesWatched: int = field(default=0)
    flaggedWatched: int = field(default=0)
    duration: int = field(default=0)
    video_id: str = field(default_factory=str)
    watched: str = field(default_factory=str)
    noNotif: bool = field(default=False)
    watched_bitfield: WatchedBitfield = field(
        init=False,
        repr=False,
        compare=False,
        default=None,
    )

    @cached_property
    def last_watched(self):
        return datetime.fromisoformat(timestamp_zone_format_switcher(self.lastWatched))

    def create_bitfield(self, video_ids: list[str]):
        self.watched_bitfield = (
            WatchedBitfield.construct_and_resize(self.watched, video_ids)
            if self.watched
            else WatchedBitfield.construct_from_array([], video_ids)
        )


@dataclass
class StremioLibrary:
    _id: str
    type: str
    state: WatchState = field(default_factory=WatchState)
    _ctime: str = field(default_factory=str)
    _mtime: str = field(default_factory=str)
    name: str = field(default_factory=str)
    poster: str = field(default_factory=str)
    background: str = field(default_factory=str)
    logo: str = field(default_factory=str)
    year: str = field(default_factory=str)
    removed: bool = field(default=True)
    temp: bool = field(default=True)
    posterShape: str = field(default="poster")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StremioLibrary:
        return json.loads(json.dumps(data), object_hook=object_hook)

    @classmethod
    def from_list(cls, data: list[dict[str, Any]]) -> list[StremioLibrary]:
        return [StremioLibrary.from_dict(a) for a in data]

    @cached_property
    def id(self):
        return self._id

    @cached_property
    def created_time(self):
        return datetime.fromisoformat(timestamp_zone_format_switcher(self._ctime))

    @cached_property
    def modified_time(self):
        return datetime.fromisoformat(timestamp_zone_format_switcher(self._mtime))

    def update_progress(
        self,
        progress: int,
        duration: int,
        video_id: str,
    ):
        state = self.state

        self._set_time(True)
        if state.video_id != video_id:
            state.video_id = video_id
            state.overallTimeWatched += state.timeWatched
            state.timeWatched = 0
            state.flaggedWatched = 0
        else:
            time_diff = max(progress - self.state.timeOffset, 0)
            state.timeWatched += time_diff
            state.overallTimeWatched += time_diff

        state.timeOffset = progress
        state.duration = duration

        if not state.flaggedWatched and state.timeWatched > (
            state.duration * STREMIO_WATCHED_COEFFICIENT
        ):
            state.flaggedWatched = 1
            state.timesWatched += 1
            if state.watched_bitfield:
                state.watched_bitfield.set_video(video_id, True)
                state.watched = state.watched_bitfield.serialize()

        if self.temp and not state.timesWatched:
            self.removed = True

        if self.removed:
            self.temp = True

    def start_stop(
        self,
        video_id: str,
        episode: Video | None,
    ):
        state = self.state
        if state.timeOffset > (state.duration * STREMIO_CREDITS_COEFFICIENT):
            from apis.StremioAPI import stremio_api

            stremio_api.get_subtitles_by_id(video_id, self.type)

            state.timeOffset = 0
            if episode and episode.next_episode:
                state.video_id = episode.next_episode.id
                state.overallTimeWatched += state.timeWatched
                state.timeWatched = 0
                state.flaggedWatched = 0
                state.timeOffset = 1
                run_plugin(
                    {
                        "mode": "playback",
                        "func": "media",
                        "media_type": self.type,
                        "id": self.id,
                        "episode": episode.next_episode.idx,
                    }
                )

    def set_library_status(self, status):
        self.removed = not status
        self.temp = False
        self.push()

    def clear_progress(self):
        self.state.timeOffset = 0
        self.push()

    def dismiss_notification(self):
        self._set_time(True)
        self.push()

    def mark_watched(self, video_id, status):
        self.state.watched_bitfield.set_video(video_id, status)
        self.state.watched = self.state.watched_bitfield.serialize()
        self.push()

    def push(self):
        from apis.StremioAPI import stremio_api

        self._set_time(False)
        stremio_api.set_data(self)
        kodi_refresh()

    def _set_time(self, set_last_watched: bool):
        now = timestamp_zone_format_switcher(
            datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        )

        self._mtime = now
        if not self._ctime:
            self._ctime = now
        if set_last_watched or not self.state.lastWatched:
            self.state.lastWatched = now


def object_hook(d: dict[str, Any]) -> [WatchState | StremioLibrary | None]:
    def filter_kwargs(cls: type, data: dict[str, Any]) -> dict[str, Any]:
        fields = get_type_hints(cls)
        return {k: v for k, v in data.items() if k in fields}

    if "_id" in d:
        return StremioLibrary(**filter_kwargs(StremioLibrary, d))
    elif "lastWatched" in d:
        return WatchState(**filter_kwargs(WatchState, d))

    return None
