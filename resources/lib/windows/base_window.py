from dataclasses import dataclass, field
from typing import (
    Generic,
    TypeVar,
    ClassVar,
)

from xbmc import LOGERROR
from xbmcgui import (
    WindowXMLDialog,
)

from addon import nas_addon
from modules.utils import log

T = TypeVar("T")


@dataclass
class BaseDialog(WindowXMLDialog, Generic[T]):
    left_action = 1
    right_action = 2
    up_action = 3
    down_action = 4
    info_action = 11
    selection_actions = (7, 100)
    closing_actions = (9, 10, 13, 92)
    context_actions = (101, 108, 117)
    choice: T | None = field(init=False, default=None)
    xml_filename: ClassVar[str]

    @classmethod
    def __new__(cls, *args, **kwargs):
        if not cls.xml_filename:
            raise ValueError(f"{cls.__name__} must define xml_filename")

        instance = super().__new__(cls, f"{cls.xml_filename}.xml", nas_addon.path)
        return instance

    def __post_init__(self):
        self.set_properties()

    def run(self):
        self.doModal()
        self.clearProperties()
        return self.choice

    def _call_control_method(self, control_id: int, method_name: str, *args):
        control = self.getControl(control_id)
        try:
            method = getattr(control, method_name)
            return method(*args)
        except Exception as e:
            log(str(e), LOGERROR)

    def get_position(self, control_id):
        return self._call_control_method(control_id, "getSelectedPosition")

    def get_list_item(self, control_id):
        return self._call_control_method(control_id, "getSelectedItem")

    def add_items(self, control_id, items):
        self._call_control_method(control_id, "addItems", items)

    def select_item(self, control_id, item):
        self._call_control_method(control_id, "selectItem", item)

    def set_image(self, control_id, image):
        self._call_control_method(control_id, "setImage", image)

    def set_label(self, control_id, label):
        self._call_control_method(control_id, "setLabel", label)

    def set_text(self, control_id, text):
        self._call_control_method(control_id, "setText", text)

    def set_percent(self, control_id, percent):
        self._call_control_method(control_id, "setPercent", percent)

    def reset_window(self, control_id: int) -> None:
        self._call_control_method(control_id, "reset")

    def set_properties(self):
        pass
