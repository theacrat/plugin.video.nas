from dataclasses import dataclass, field
from typing import TypeVar, Generic

from xbmc import getInfoLabel
from xbmcgui import ListItem

from addon import nas_addon
from modules.utils import thread_function

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
        def _build_content(item: T) -> tuple[str, ListItem, bool] | None:
            return self._build_content(item, data.index(item))

        return thread_function(_build_content, data)
