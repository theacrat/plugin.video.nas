from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from classes.StremioSubtitle import StremioSubtitle
from classes.base_class import StremioObject


@dataclass
class BehaviorHints(StremioObject):
    countryWhitelist: str | None = field(default=None)
    notWebReady: bool | None = field(default=None)
    proxyHeaders: str | None = field(default=None)
    videoHash: str | None = field(default=None)
    videoSize: int | None = field(default=None)
    filename: str | None = field(default=None)


@dataclass
class StremioStream(StremioObject):
    url: str | None = field(default=None)
    ytId: str | None = field(default=None)
    infoHash: str | None = field(default=None)
    fileIdx: int | None = field(default=None)
    externalUrl: str | None = field(default=None)

    name: str | None = field(default=None)
    description: str | None = field(default=None)
    subtitles: list[StremioSubtitle] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    behaviorHints: BehaviorHints = field(default_factory=BehaviorHints)

    @classmethod
    def transform_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        if "title" in data:
            data["description"] = data["title"]
        return super().transform_dict(data)

    def __post_init__(self):
        if not any([self.url, self.ytId, self.infoHash, self.externalUrl]):
            raise ValueError("No resource given")
