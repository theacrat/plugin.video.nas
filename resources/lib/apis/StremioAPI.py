import codecs
import datetime
import json
import requests.adapters
from dataclasses import dataclass, field
from functools import reduce
from itertools import chain
from typing import Any, Callable

import xbmc
from xbmcgui import Dialog

from addon import nas_addon
from classes.StremioAddon import (
    Resource,
    StremioAddon,
    Catalog,
    ExtraType,
    AddonType,
)
from classes.StremioLibrary import StremioLibrary
from classes.StremioMeta import StremioMeta, StremioType
from classes.StremioStream import StremioStream
from classes.StremioSubtitle import StremioSubtitle
from modules.utils import (
    get_setting,
    kodi_refresh,
    log,
    set_setting,
    thread_function,
    classes_from_list,
)


@dataclass
class StremioAPI:
    token: str = field(init=False)
    addons: list[StremioAddon] = field(init=False, default_factory=list)
    catalogs: list[Catalog] = field(init=False, default_factory=list)
    metadata: dict[str, StremioMeta] = field(init=False, default_factory=dict)
    data_store: dict[str, StremioLibrary] = field(init=False, default_factory=dict)
    session: requests.Session = field(init=False, default_factory=requests.Session)
    addons_updated: datetime.datetime = field(
        init=False, default_factory=lambda: datetime.datetime.now()
    )
    data_store_cache: str = field(
        init=False, default_factory=lambda: nas_addon.get_file_path("datastore.json")
    )

    def __post_init__(self):
        self.token = get_setting("stremio.token")

        adapter = requests.adapters.HTTPAdapter()
        self.session.mount("https://", adapter)
        self.session.headers.update({"User-Agent": "Stremio"})
        self.get_addons()
        self.get_data_store()

    @property
    def library(self) -> dict[str, StremioLibrary]:
        return self.data_store

    @property
    def home_catalogs(self):
        return self._filter_catalogs()

    @property
    def discover_catalogs(self) -> list[Catalog]:
        return self._filter_catalogs(ExtraType.DISCOVER)

    @property
    def search_catalogs(self) -> list[Catalog]:
        return self._filter_catalogs(ExtraType.SEARCH)

    @property
    def notification_catalogs(self) -> list[Catalog]:
        return self._filter_catalogs(ExtraType.NOTIFICATION)

    def _get(self, url: str, default_return=None):
        if default_return is None:
            default_return = {}
        response = None
        log(url, xbmc.LOGINFO)
        try:
            response = self.session.get(f"{url}.json", timeout=20)
            return response.json()
        except Exception as e:
            log(str(e), xbmc.LOGERROR)
            if response:
                log(str(response), xbmc.LOGERROR)
            return default_return

    def _post(self, url: str, post_data=None, default_return=None):
        if default_return is None:
            default_return = {}
        if post_data is None:
            post_data = {}
        response = None
        if self.token:
            post_data["authKey"] = self.token
        try:
            log(url, xbmc.LOGINFO)
            response = self.session.post(
                f"https://api.strem.io/api/{url}", json=post_data, timeout=20
            )
            return response.json().get("result", {})
        except Exception as e:
            log(str(e), xbmc.LOGERROR)
            if response:
                log(str(response), xbmc.LOGERROR)
            return default_return

    def _filter_addons(
        self,
        addon_type: str,
        content_type: str,
        content_id: str = None,
        refresh: bool = False,
    ) -> list[StremioAddon]:
        matching_addons = []
        addons = self.get_addons(refresh)
        log(f"{content_type} {addon_type} {content_id}")
        for a in addons:
            m = a.manifest

            if (
                addon_type in m.resources
                and (content_type in m.types or content_type is None)
                and (
                    None in [m.idPrefixes, content_id]
                    or any(content_id.startswith(i) for i in m.idPrefixes)
                )
            ):
                matching_addons.append(a)
                continue

            for r in [r for r in m.resources if type(r) == Resource]:
                if (
                    r.name == addon_type
                    and (content_type in r.types or content_type is None)
                    and (
                        None in [r.idPrefixes, content_id]
                        or any(content_id.startswith(i) for i in r.idPrefixes)
                    )
                ):
                    matching_addons.append(a)
        return matching_addons

    # TODO qr code login
    def login(self):
        if not (username := Dialog().input("Email")):
            return
        if not (password := Dialog().input("Password")):
            return

        post_data = {"email": username, "password": password}
        result = self._post("login", post_data)
        set_setting("stremio.token", result["authKey"])
        set_setting("stremio.user", result["user"]["email"])
        self.token = get_setting("stremio.token")
        kodi_refresh()

    def logout(self):
        self._post("logout")
        set_setting("stremio.token", "")
        set_setting("stremio.user", "")
        self.token = get_setting("stremio.token")

        import os

        os.remove(self.data_store_cache)

    def get_addons(self, refresh: bool = False) -> list[StremioAddon]:
        if (
            not self.addons
            or refresh
            or (datetime.datetime.now() - self.addons_updated).total_seconds() > 300
        ):
            self.addons_updated = datetime.datetime.now()
            response = self._post("addonCollectionGet", {"update": True})
            self.addons = classes_from_list(StremioAddon, response.get("addons", []))
            self.catalogs = list(chain(*[a.manifest.catalogs for a in self.addons]))
        return self.addons

    def write_data_store(self):
        with open(self.data_store_cache, "wb") as f:
            json.dump(
                [i.as_dict() for i in self.data_store.values()],
                codecs.getwriter("utf-8")(f),
                ensure_ascii=False,
            )

    def load_data_store(self):
        try:
            with open(self.data_store_cache) as f:
                return json.load(f)
        except Exception as e:
            log(str(e), xbmc.LOGERROR)
            return None

    def get_data_store(self, refresh: bool = False) -> dict[str, StremioLibrary]:
        if not self.data_store or refresh:
            cached_store = self.load_data_store()
            response = cached_store
            if not response or refresh:
                response = self._post(
                    "datastoreGet", {"all": True, "collection": "libraryItem"}
                )
            self.data_store = {
                i.id: i for i in classes_from_list(StremioLibrary, response)
            }
            if cached_store and not refresh:
                self.update_data_store()
            self.write_data_store()
        return self.data_store

    def update_data_store(self):
        data_store = self.data_store
        meta = self._post("datastoreMeta", {"collection": "libraryItem"})
        outdated_ids = []
        for i in meta:
            if i[0] not in data_store or data_store[
                i[0]
            ].mtime < datetime.datetime.fromtimestamp(
                i[1] / 1000, datetime.timezone.utc
            ):
                outdated_ids.append(i[0])

        if not len(outdated_ids):
            return

        self.get_data_by_ids(outdated_ids)
        self.write_data_store()

    def get_data_by_ids(self, ids: list[str]):
        response = self._post(
            "datastoreGet",
            {"ids": ids, "collection": "libraryItem"},
        )
        for i in classes_from_list(StremioLibrary, response):
            self.data_store[i.id] = i

    def get_data_by_meta(self, meta: StremioMeta) -> StremioLibrary | None:
        data_store = self.get_data_store()
        return (
            data_store[meta.id]
            if meta.id in data_store
            else StremioLibrary(**{"_id": meta.id, **meta.as_dict()})
        )

    def set_data(self, data: StremioLibrary):
        self.data_store[data.id] = data
        self.write_data_store()
        post_data = {"collection": "libraryItem", "changes": [data.as_dict()]}
        self._post("datastorePut", post_data)

    def get_library_types(self) -> list[str]:
        types = []
        for k, v in self.get_data_store().items():
            if v.type not in types and not (v.removed or v.temp):
                types.append(v.type)
        types.sort(key=StremioType.get_sort_key)
        types.insert(0, "all")
        return types

    def get_library(self, type_filter: str | None = None) -> list[StremioMeta]:
        responses = [
            StremioMeta(**{"id": i.id, **i.as_dict()})
            for i in sorted(
                [v for k, v in self.get_data_store().items() if not v.removed],
                key=lambda e: e.state.lastWatched,
                reverse=True,
            )
            if type_filter is None or i.type == type_filter
        ]
        return responses

    def get_metadata_by_libraries(
        self, libraries: list[StremioLibrary]
    ) -> list[StremioMeta]:
        def _get_meta(item: StremioLibrary):
            return self.get_metadata_by_id(item.id, item.type)

        return [r for r in thread_function(_get_meta, libraries) if r]

    def get_metadata_by_id(
        self, content_id: str, content_type: str, refresh=False
    ) -> StremioMeta:
        def _get_meta(item: StremioAddon):
            response = self._get(
                f"{item.base_url}/{AddonType.META}/{content_type}/{content_id}"
            )
            return response.get("meta", {})

        if content_id not in self.metadata or refresh:
            meta_addons = list(
                self._filter_addons(AddonType.META, content_type, content_id)
            )

            results = thread_function(_get_meta, meta_addons)

            self.metadata[content_id] = StremioMeta(
                **reduce(lambda a, b: {**b, **a}, results)
            )
        return self.metadata[content_id]

    def get_streams_by_id(
        self,
        content_id: str,
        content_type: str,
        callback: Callable[[list[StremioStream], int, int], Any],
    ):
        stream_addons = self._filter_addons(
            AddonType.STREAM, content_type, content_id, True
        )

        def _get_stream(item: StremioAddon):
            response = self._get(
                f"{item.base_url}/{AddonType.STREAM}/{content_type}/{content_id}"
            )
            streams = classes_from_list(StremioStream, response.get("streams", []))
            callback(streams, stream_addons.index(item), len(stream_addons))

        thread_function(_get_stream, stream_addons)

    def get_subtitles_by_id(
        self, content_id: str, content_type: str
    ) -> list[StremioSubtitle]:
        def _get_subs(item: StremioAddon):
            response = self._get(
                f"{item.base_url}/{AddonType.SUBTITLES}/{content_type}/{content_id}"
            )
            return classes_from_list(StremioSubtitle, response.get("subtitles", []))

        sub_addons = self._filter_addons(AddonType.SUBTITLES, content_type, content_id)

        return list(chain(*thread_function(_get_subs, sub_addons)))

    def _filter_catalogs(self, extra: str | None = None) -> list[Catalog]:
        return [
            c
            for c in self.catalogs
            if (
                not extra
                or any(e.name == extra for e in c.extra)
                or extra in c.extraSupported
            )
            and (
                (extra and not any(e != extra for e in c.extraRequired))
                or (
                    not extra
                    and not any(e.isRequired for e in c.extra)
                    and not c.extraRequired
                )
            )
        ]

    def get_discover_types(self) -> list[str]:
        types = list({c.type for c in self.discover_catalogs})
        types.sort(key=StremioType.get_sort_key)
        return types

    def get_discover_catalogs_by_type(self, catalog_type: str) -> list[Catalog]:
        return [c for c in self.discover_catalogs if c.type == catalog_type]

    def get_notifications(self, library_items: list[StremioMeta]):
        def _get_notification_catalog(catalog: Catalog):
            ids = [
                l.id
                for l in library_items
                if any(
                    l.id.startswith(prefix)
                    for prefix in catalog.addon.manifest.idPrefixes
                )
            ]

            if not len(ids):
                return []

            return self.get_catalog(
                catalog,
                ExtraType.NOTIFICATION,
                ids,
            )

        catalogs = self.notification_catalogs

        return list(chain(*thread_function(_get_notification_catalog, catalogs)))

    def get_catalog(
        self,
        catalog: Catalog,
        extra_type: str = None,
        extra_query: str | list[str] = None,
    ) -> list[StremioMeta | None]:
        query = (
            f"{catalog.addon.base_url}/{AddonType.CATALOG}/{catalog.type}/{catalog.id}"
        )
        if extra_type and extra_query:
            query = f"{query}/{extra_type}={','.join(extra_query) if type(extra_query) is list else extra_query}"

        response = self._get(query)
        meta = response.get("metas", []) or response.get("metasDetailed", [])

        return classes_from_list(StremioMeta, meta)

    def send_events(self, events):
        return self._post("events", {"events": events})


stremio_api = StremioAPI()
