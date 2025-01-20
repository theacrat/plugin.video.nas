from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Union, get_type_hints


@dataclass
class Extra:
    name: str
    isRequired: bool = field(default=False)
    options: list[str] = field(default_factory=list)
    optionsLimit: int | None = field(default=None)


@dataclass
class StremioCatalog:
    id: str
    type: str
    name: str = field(default_factory=str)
    extra: list[Extra] = field(default_factory=list)
    extraRequired: list[str] = field(default_factory=list)
    extraSupported: list[str] = field(default_factory=list)
    addon: StremioAddon = field(init=False, repr=False, compare=False, default=None)

    @cached_property
    def title(self):
        return f"{self.name} - {self.type[:1].upper()}{self.type[1:]}"


@dataclass
class Resource:
    name: str
    types: list[str] = field(default_factory=list)
    idPrefixes: list[str] = field(default_factory=list)


@dataclass
class BehaviorHints:
    adult: bool | None = field(default=None)
    p2p: bool | None = field(default=None)
    configurable: bool | None = field(default=None)
    configurationRequired: bool | None = field(default=None)


@dataclass
class Manifest:
    id: str
    version: str
    name: str
    description: str
    types: list[str]
    catalogs: list[StremioCatalog]
    resources: list[Union[Resource, str]]
    behaviorHints: BehaviorHints = field(default_factory=BehaviorHints)
    addonCatalogs: list[StremioCatalog] = field(default_factory=list)
    contactEmail: str | None = field(default=None)
    logo: str | None = field(default=None)
    background: str | None = field(default=None)
    idPrefixes: list[str] = field(default_factory=list)


@dataclass
class Flags:
    official: bool
    protected: bool


@dataclass
class StremioAddon:
    transportUrl: str
    transportName: str
    manifest: Manifest
    flags: Flags
    legacy: bool = field(init=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StremioAddon:
        return json.loads(json.dumps(data), object_hook=object_hook)

    @classmethod
    def from_list(cls, data: list[dict[str, Any]]) -> list[StremioAddon]:
        return [StremioAddon.from_dict(a) for a in data]

    @cached_property
    def base_url(self):
        return self.transportUrl.split("/manifest.json")[0]

    def __post_init__(self):
        self.legacy = not self.transportUrl.endswith("manifest.json")
        for c in self.manifest.catalogs:
            c.addon = self
            if not c.name:
                c.name = self.manifest.name


def object_hook(
    d: dict[str, Any]
) -> [
    Extra
    | StremioCatalog
    | Resource
    | BehaviorHints
    | Manifest
    | Flags
    | StremioAddon
    | None
]:
    def filter_kwargs(cls: type, data: dict[str, Any]) -> dict[str, Any]:
        fields = get_type_hints(cls)
        return {k: v for k, v in data.items() if k in fields}

    if all(k in d for k in ("transportUrl", "transportName", "manifest", "flags")):
        return StremioAddon(**filter_kwargs(StremioAddon, d))
    elif all(k in d for k in ("id", "version", "name")):
        return Manifest(**filter_kwargs(Manifest, d))
    elif all(k in d for k in ("name", "types", "idPrefixes")):
        return Resource(**filter_kwargs(Resource, d))
    elif all(k in d for k in ("id", "type")):
        return StremioCatalog(**filter_kwargs(StremioCatalog, d))
    elif (
        "name" in d
        and len(d) == 1
        or any(k in d for k in ("options", "isRequired", "optionsLimit"))
    ):
        return Extra(**filter_kwargs(Extra, d))
    elif any(k in d for k in get_type_hints(BehaviorHints)):
        return BehaviorHints(**filter_kwargs(BehaviorHints, d))
    elif all(k in d for k in get_type_hints(Flags)):
        return Flags(**filter_kwargs(Flags, d))
    return
