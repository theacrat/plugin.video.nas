from __future__ import annotations

from dataclasses import dataclass

from classes.base_class import StremioObject


@dataclass
class StremioSubtitle(StremioObject):
    id: str
    url: str
    lang: str
