from dataclasses import dataclass, field
from itertools import chain
from typing import Callable

from xbmcgui import ListItem

from addon import nas_addon
from classes.StremioMeta import StremioMeta
from classes.StremioStream import StremioStream
from indexers.base_indexer import NASListItem
from modules.kodi_utils import (
    hide_busy_dialog,
    notification,
)
from windows.base_window import BaseDialog


@dataclass
class SourcesResults(BaseDialog[StremioStream]):
    pre_scrape: bool = field(default=None)
    meta: StremioMeta = field(default=None)
    episode: int = field(default=None)
    results: list[list[StremioStream]] = field(default_factory=list)
    result_listeners: list[Callable[[int], None]] = field(default_factory=list)
    window_id: int = field(init=False, default=2002)
    item_list: list[list[ListItem]] = field(init=False, default_factory=list)
    xml_filename = "sources_results"

    def onInit(self):
        self.result_listeners.append(self.update_items)
        self.update_items()
        self.setFocusId(self.window_id)

    def set_item_list(self, position):
        if (min_len := position + 1) > len(self.item_list):
            self.item_list.extend(
                [] for _ in range((len(self.results) or min_len) - len(self.item_list))
            )
        self.item_list[position] = self.make_items(position)

    def update_items(self, position=None):
        if position is None:
            for idx, r in enumerate(self.results):
                if r is None or self.item_list:
                    continue
                self.set_item_list(idx)
        else:
            self.set_item_list(position)

        selected_position = self.get_position(self.window_id)
        selected_item = self.get_list_item(self.window_id)
        self.reset_window(self.window_id)
        chain_list = list(chain(*self.item_list))
        if not len(chain_list) and not None in self.results:
            notification("No results found")
            self.close()
            return
        self.add_items(self.window_id, chain_list)
        self.setFocusId(self.window_id)
        if not selected_position:
            self.select_item(self.window_id, 0)
        elif selected_item:
            a_idx = selected_item.getProperty("addon_idx")
            s_idx = selected_item.getProperty("stream_idx")
            self.select_item(
                self.window_id,
                next(
                    (
                        idx
                        for idx, s in enumerate(chain_list)
                        if s.getProperty("addon_idx") == a_idx
                        and s.getProperty("stream_idx") == s_idx
                    ),
                    0,
                ),
            )
        else:
            self.select_item(self.window_id, 0)
        remaining_sources = sum(s is None for s in self.results)
        self.setProperty(
            "remaining_sources",
            (
                f"{remaining_sources} addon{'s are' if remaining_sources != 1 else ' is'} still loading"
                if remaining_sources
                else ""
            ),
        )

    def run(self):
        super().run()
        hide_busy_dialog()
        return self.choice

    def close(self) -> None:
        self.result_listeners.remove(self.update_items)
        super().close()

    def onAction(self, action):
        selected_item = self.get_list_item(self.window_id)

        if action in self.selection_actions:
            addon_idx = int(selected_item.getProperty("addon_idx"))
            stream_idx = int(selected_item.getProperty("stream_idx"))
            self.choice = self.results[addon_idx][stream_idx]
            self.close()
        elif action in self.closing_actions:
            self.close()

    def make_items(self, addon_idx):
        items = []
        for count, item in enumerate(self.results[addon_idx]):
            list_item = NASListItem()
            set_properties = list_item.setProperties

            set_properties(
                {
                    "name": item.name.replace("\n", "[CR]"),
                    "description": (item.description or item.title).replace(
                        "\n", "[CR]"
                    ),
                    "hash": item.hash,
                    "url": item.url,
                    "addon_idx": addon_idx,
                    "stream_idx": count,
                }
            )
            items.append(list_item)
        return items

    def set_properties(self):
        self.setProperty("fanart", self.meta.background or nas_addon.fanart)
        self.setProperty("clearlogo", self.meta.logo)
        self.setProperty("title", self.meta.name)
        self.setProperty("total_results", "0")
