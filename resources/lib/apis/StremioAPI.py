from dataclasses import dataclass, field
from functools import reduce
from itertools import chain
from threading import Thread
from typing import Callable, Any

import xbmc
from xbmcgui import Dialog

from classes.StremioAddon import Resource, StremioAddon, StremioCatalog
from classes.StremioLibrary import StremioLibrary
from classes.StremioMeta import StremioMeta
from classes.StremioStream import StremioStream
from modules.kodi_utils import (
    log,
    dataclass_to_dict,
    set_setting,
    kodi_refresh,
    get_setting,
)

API_ENDPOINT = "https://api.strem.io/api/"
timeout = 20

import requests.adapters


@dataclass
class StremioAPI:
    token: str = field(init=False)
    addons: list[StremioAddon] = field(init=False, default_factory=list)
    catalogs: list[StremioCatalog] = field(init=False, default_factory=list)
    metadata: dict[str, StremioMeta] = field(init=False, default_factory=dict)
    data_store: dict[str, StremioLibrary] = field(init=False, default_factory=dict)
    session: requests.Session = field(init=False, default_factory=requests.Session)

    def __post_init__(self):
        self.token = get_setting("stremio.token")
        self.get_addons()
        self.get_data_store()

        adapter = requests.adapters.HTTPAdapter()
        self.session.mount("https://", adapter)
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            }
        )

    @property
    def library(self) -> dict[str, StremioLibrary]:
        return self.data_store

    def _get(self, url: str, default_return=None):
        if default_return is None:
            default_return = {}
        response = None
        log(url, xbmc.LOGINFO)
        url = url.replace("/manifest.json", "")
        try:
            response = self.session.get(url, timeout=timeout)
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
                f"{API_ENDPOINT}{url}", json=post_data, timeout=timeout
            )
            return response.json().get("result", {})
        except Exception as e:
            log(str(e), xbmc.LOGERROR)
            if response:
                log(str(response), xbmc.LOGERROR)
            return default_return

    def _filter_addons(
        self, addon_type: str, media_type: str, id: str = None
    ) -> list[StremioAddon]:
        matching_addons = []
        for a in self.get_addons():
            m = a.manifest
            if (
                addon_type in m.resources
                and (media_type in m.types or media_type is None)
                and (
                    None in [m.idPrefixes, id]
                    or any(id.startswith(i) for i in m.idPrefixes)
                )
            ):
                matching_addons.append(a)
                continue

            for r in [r for r in m.resources if type(r) == Resource]:
                if (
                    r.name == addon_type
                    and (media_type in r.types or media_type is None)
                    and (
                        None in [r.idPrefixes, id]
                        or any(id.startswith(i) for i in r.idPrefixes)
                    )
                ):
                    matching_addons.append(a)
        return matching_addons

    # TODO qr code login
    def login(self):
        username = Dialog().input("Email")
        if not username:
            return
        password = Dialog().input("Password")
        if not password:
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

    def get_addons(self, refresh: bool = False) -> list[StremioAddon]:
        if not self.addons or refresh:
            response = self._post("addonCollectionGet", {"update": True})
            self.addons = StremioAddon.from_list(response.get("addons", []))
        return self.addons

    def get_catalogs(self, refresh: bool = False) -> list[StremioCatalog]:
        if not self.catalogs or refresh:
            addons = self.get_addons(refresh)
            self.catalogs = list(chain(*[a.manifest.catalogs for a in addons]))
        return self.catalogs

    def get_data_store(self, refresh: bool = False) -> dict[str, StremioLibrary]:
        if not self.data_store or refresh:
            response = self._post(
                "datastoreGet", {"all": True, "collection": "libraryItem"}
            )
            self.data_store = {i.id: i for i in StremioLibrary.from_list(response)}
        return self.data_store

    def get_data_by_metas(
        self, metas: list[StremioMeta], refresh: bool = False
    ) -> list[StremioLibrary]:
        data_store = self.get_data_store()
        uncached_ids = [i.id for i in metas if i.id not in data_store or refresh]
        if uncached_ids:
            response = self._post(
                "datastoreGet", {"ids": uncached_ids, "collection": "libraryItem"}
            )
            for i in StremioLibrary.from_list(response):
                self.data_store[i.id] = i
        for i in [i for i in metas if i.id not in data_store]:
            self.data_store[i.id] = StremioLibrary.from_dict(
                {"_id": i.id, **dataclass_to_dict(i)}
            )

        library_items = [data_store[i.id] for i in metas]
        for idx, i in enumerate(library_items):
            meta = metas[idx]
            if not i.state.watched_bitfield and meta.videos:
                i.state.create_bitfield([v.id for v in meta.videos])
        return library_items

    def get_data_by_meta(
        self, meta: StremioMeta, refresh: bool = False
    ) -> StremioLibrary:
        return self.get_data_by_metas([meta], refresh)[0]

    def set_data(self, data: StremioLibrary):
        self.data_store[data.id] = data
        post_data = {"collection": "libraryItem", "changes": [dataclass_to_dict(data)]}
        self._post("datastorePut", post_data)

    def get_library_types(self) -> list[str]:
        types = []
        for k, v in self.get_data_store().items():
            if v.type not in types and not (v.removed or v.temp):
                types.append(v.type)
        types.sort(key=lambda c: (0 if c == "movie" else 1 if c == "series" else 2, c))
        types.insert(0, "all")
        return types

    def get_library(self, type_filter: str | None = None) -> list[StremioMeta]:
        responses = []

        def _get_meta(item: StremioLibrary, idx):
            responses[idx] = self.get_metadata_by_id(item.id, item.type)

        entries = [
            i
            for i in sorted(
                [v for k, v in self.get_data_store().items() if not v.removed],
                key=lambda e: e.state.lastWatched,
                reverse=True,
            )
            if type_filter is None or i.type == type_filter
        ]
        responses.extend(None for _ in entries)

        threads = [
            Thread(target=_get_meta, args=(item, idx))
            for idx, item in enumerate(entries)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return responses

    def get_metadata_by_libraries(
        self, libraries: list[StremioLibrary]
    ) -> list[StremioMeta]:
        responses = []

        def _get_meta(item: StremioLibrary, idx):
            responses[idx] = self.get_metadata_by_id(item.id, item.type)

        responses.extend(None for _ in libraries)
        threads = [
            Thread(target=_get_meta, args=(item, idx))
            for idx, item in enumerate(libraries)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return responses

    def get_metadata_by_id(
        self, id: str, media_type: str, refresh=False
    ) -> StremioMeta:
        responses = []

        def _get_meta(item: StremioAddon, idx: int):
            response = self._get(f"{item.base_url}/meta/{media_type}/{id}.json")
            responses[idx] = response.get("meta", {})

        if id not in self.metadata or refresh:
            meta_addons = list(self._filter_addons("meta", media_type, id))
            responses.extend(None for _ in meta_addons)

            threads = [
                Thread(target=_get_meta, args=(item, idx))
                for idx, item in enumerate(meta_addons)
            ]
            [t.start() for t in threads]
            [t.join() for t in threads]
            self.metadata[id] = StremioMeta.from_dict(
                reduce(lambda a, b: {**b, **a}, responses)
            )
        return self.metadata[id]

    def get_streams_by_id(
        self,
        id: str,
        media_type: str,
        results: list[dict, None],
        callback: Callable[[list[StremioStream], int], Any],
    ) -> list[Thread]:
        def _get_stream(item: StremioAddon, idx: int):
            response = self._get(f"{item.base_url}/stream/{media_type}/{id}.json")
            streams = StremioStream.from_list(response.get("streams", []))
            callback(streams, idx)

        stream_addons = self._filter_addons("stream", media_type, id)
        results.extend(None for _ in stream_addons)
        threads = [
            Thread(target=_get_stream, args=(item, idx))
            for idx, item in enumerate(stream_addons)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return threads

    # not really used to get subtitles at the moment just for pinging syncribullet and co
    def get_subtitles_by_id(self, id: str, media_type: str) -> list[dict]:
        responses: list[dict] = []

        def _get_subs(item: StremioAddon, idx: int):
            response = self._get(f"{item.base_url}/subtitles/{media_type}/{id}.json")
            responses.append(response.get("subtitles", {}))

        sub_addons = self._filter_addons("subtitles", media_type, id)
        threads = [
            Thread(target=_get_subs, args=(item, idx))
            for idx, item in enumerate(sub_addons)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return list(chain(*responses))

    def get_home_catalogs(self) -> list[StremioCatalog]:
        log("Getting home catalogs")
        return [
            c
            for c in self.get_catalogs()
            if not any(e.isRequired for e in c.extra) and len(c.extraRequired) == 0
        ]

    def get_discover_catalogs(self) -> list[StremioCatalog]:
        return [
            c
            for c in self.get_catalogs()
            if (any(e.name == "genre" for e in c.extra) or "genre" in c.extraSupported)
            and not any(e != "genre" for e in c.extraRequired)
        ]

    def get_discover_types(self) -> list[str]:
        types = []
        catalogs = self.get_discover_catalogs()
        for catalog in catalogs:
            if catalog.type not in types:
                types.append(catalog.type)
        types.sort(key=lambda c: (0 if c == "movie" else 1 if c == "series" else 2, c))
        return types

    def get_discover_catalogs_by_type(self, type: str) -> list[StremioCatalog]:
        return [c for c in self.get_discover_catalogs() if c.type == type]

    def get_search_catalogs(self) -> list[StremioCatalog]:
        return [
            c
            for c in self.get_catalogs()
            if (
                any(e.name == "search" for e in c.extra) or "search" in c.extraSupported
            )
            and not any(e != "search" for e in c.extraRequired)
        ]

    def get_notification_catalogs(self) -> list[StremioCatalog]:
        return [
            c
            for c in self.get_catalogs()
            if (
                any(e.name == "lastVideosIds" for e in c.extra)
                or "lastVideosIds" in c.extraSupported
            )
            and not any(e != "lastVideosIds" for e in c.extraRequired)
        ]

    def get_catalog(
        self,
        catalog: StremioCatalog,
        genre: str = None,
        search: str = None,
        notification_ids=None,
    ) -> list[StremioMeta | None]:
        responses: list[StremioMeta | None] = []

        def _get_full_meta(item, idx):
            responses[idx] = self.get_metadata_by_id(item.get("id"), item.get("type"))

        query = "/".join(
            filter(
                None,
                [
                    catalog.addon.base_url,
                    "catalog",
                    catalog.type,
                    catalog.id,
                    genre,
                    search,
                    notification_ids,
                ],
            )
        )

        response = self._get(f"{query}.json").get("metas", [])

        responses.extend(None for _ in response)

        threads = [
            Thread(target=_get_full_meta, args=(item, idx))
            for idx, item in enumerate(response)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return responses

    def send_events(self, events):
        return self._post("events", {"events": events})


stremio_api = StremioAPI()
