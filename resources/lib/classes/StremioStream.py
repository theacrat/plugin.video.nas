from __future__ import annotations

import json
from dataclasses import dataclass
from typing import get_type_hints, Any


@dataclass
class BehaviorHints:
    bingeGroup: str | None = None
    filename: str | None = None
    notWebReady: bool | None = None
    videoSize: int | None = None


@dataclass
class StremioStream:
    name: str
    url: str | None = None
    title: str | None = None
    description: str | None = None
    behaviorHints: BehaviorHints | None = None
    hash: str | None = None
    infoHash: str | None = None
    fileIdx: int | None = None
    magnet: str | None = None
    nzb: str | None = None
    seeders: int | None = None
    peers: int | None = None
    quality: str | None = None
    resolution: str | None = None
    language: str | None = None
    is_cached: bool | None = None
    size: int | None = None
    type: str | None = None
    adult: bool | None = None
    sources: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StremioStream:
        return json.loads(json.dumps(data), object_hook=object_hook)

    @classmethod
    def from_list(cls, data: list[dict[str, Any]]) -> list[StremioStream]:
        return [StremioStream.from_dict(a) for a in data]


def object_hook(d: dict[str, Any]) -> [StremioStream | BehaviorHints | None]:
    def filter_kwargs(cls: type, data: dict[str, Any]) -> dict[str, Any]:
        fields = get_type_hints(cls)
        return {k: v for k, v in data.items() if k in fields}

    if "name" in d:
        return StremioStream(**filter_kwargs(StremioStream, d))
    elif any(k in d for k in get_type_hints(BehaviorHints)):
        return BehaviorHints(**filter_kwargs(BehaviorHints, d))

    return
