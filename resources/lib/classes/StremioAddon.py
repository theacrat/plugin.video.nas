from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from functools import cached_property

from classes.base_class import StremioObject


class ExtraType(StrEnum):
    SEARCH = auto()
    NOTIFICATION = "lastVideosIds"
    DISCOVER = "genre"


class AddonType(StrEnum):
    CATALOG = auto()
    META = auto()
    STREAM = auto()
    SUBTITLES = auto()


@dataclass
class Extra(StremioObject):
    name: str
    isRequired: bool = field(default=False)
    options: list[str] = field(default_factory=list)
    optionsLimit: int | None = field(default=None)


@dataclass
class Catalog(StremioObject):
    id: str
    type: str
    name: str = field(default_factory=str)
    extra: list[Extra] = field(default_factory=list)
    extraRequired: list[str] = field(default_factory=list)
    extraSupported: list[str] = field(default_factory=list)
    addon: StremioAddon = field(init=False, repr=False, compare=False)

    @cached_property
    def title(self):
        return f"{self.name} - {self.type[:1].upper()}{self.type[1:]}"


@dataclass
class Resource(StremioObject):
    name: str
    types: list[str] = field(default_factory=list)
    idPrefixes: list[str] = field(default_factory=list)


@dataclass
class BehaviorHints(StremioObject):
    adult: bool | None = field(default=None)
    p2p: bool | None = field(default=None)
    configurable: bool | None = field(default=None)
    configurationRequired: bool | None = field(default=None)


@dataclass
class Manifest(StremioObject):
    id: str
    version: str
    name: str
    description: str
    types: list[str]
    catalogs: list[Catalog]
    resources: list[Resource | str]
    behaviorHints: BehaviorHints = field(default_factory=BehaviorHints)
    addonCatalogs: list[Catalog] = field(default_factory=list)
    contactEmail: str | None = field(default=None)
    logo: str | None = field(default=None)
    background: str | None = field(default=None)
    idPrefixes: list[str] = field(default_factory=list)


@dataclass
class Flags(StremioObject):
    official: bool = field(default_factory=bool)
    protected: bool = field(default_factory=bool)


@dataclass
class StremioAddon(StremioObject):
    transportUrl: str
    transportName: str
    manifest: Manifest
    flags: Flags

    @cached_property
    def legacy(self):
        return not self.transportUrl.endswith("manifest.json")

    @cached_property
    def base_url(self):
        return self.transportUrl.split("/manifest.json")[0]

    def __post_init__(self):
        for c in self.manifest.catalogs:
            c.addon = self
            if not c.name and self.manifest:
                c.name = self.manifest.name
