from dataclasses import dataclass, field
from threading import Thread
from typing import TypeVar, Generic

from xbmc import getInfoLabel
from xbmcgui import ListItem

from addon import nas_addon

T = TypeVar("T")


@dataclass
class NASListItem(ListItem):
    def __post_init__(self):
        super().__init__(offscreen=True)


@dataclass
class BaseIndexer(Generic[T]):
    external: bool = field(
        init=False,
        default=lambda: nas_addon.name != getInfoLabel("Container.PluginName"),
    )
    refreshed: [bool | None]

    def _build_content(self, item: T, position: int) -> tuple[str, ListItem, bool]:
        raise NotImplementedError("Subclasses must implement build_content")

    def _worker(self, data: list[T]) -> list[tuple[str, ListItem, bool] | None]:
        items: list[tuple[str, ListItem, bool] | None] = [None] * len(data)

        def _build_content(item: T, idx: int) -> None:
            items[idx] = self._build_content(item, idx)

        threads = [
            Thread(target=_build_content, args=(item, idx))
            for idx, item in enumerate(data)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return items
