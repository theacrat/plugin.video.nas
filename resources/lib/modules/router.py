from typing import Any, TypeVar, get_type_hints
from urllib.parse import parse_qsl

from indexers.base_indexer import BaseIndexer
from indexers.navigator import Navigator
from modules.kodi_utils import external, parse_string


def sys_exit_check():
    return external()


T = TypeVar("T")


def build_class(cls: type[T], data: dict[str, Any]) -> T:
    fields = get_type_hints(cls)
    filtered = {k: v for k, v in data.items() if k in fields}
    return cls(**filtered)


def routing(sys):
    params = dict(parse_qsl(sys.argv[2][1:], keep_blank_values=True))
    parsed_params = {k: parse_string(v) for k, v in params.items()}

    mode = params.get("mode", "navigator.main")
    if parsed_params.get("mode", None):
        del parsed_params["mode"]
    if "navigator." in mode:
        navigator = build_class(Navigator, parsed_params)
        match mode:
            case "navigator.main":
                return navigator.main()
            case "navigator.home":
                return navigator.home()
            case "navigator.discover":
                return navigator.discover()
            case "navigator.library":
                return navigator.library()
            case "navigator.search":
                return navigator.search()
            case "navigator.settings":
                return navigator.settings()
    if "playback." in mode:
        if mode == "playback.media":
            from modules.sources import Sources

            return build_class(Sources, parsed_params).play()
    if "choice" in mode:
        return exec("dialogs.%s(params)" % mode)
    if "build" in mode:
        parsed_params["refreshed"] = parsed_params.get("refreshed", False)

        selected_class: type[BaseIndexer | None] = None
        match mode:
            case "build_catalog":
                from indexers.catalog import Catalog

                selected_class = Catalog
            case "build_discover":
                from indexers.discover import Discover

                selected_class = Discover
            case "build_seasons":
                from indexers.seasons import Seasons

                selected_class = Seasons
            case "build_episodes":
                from indexers.episodes import Episodes

                selected_class = Episodes

        return build_class(selected_class, parsed_params) if selected_class else None

    if "library." in mode:
        from modules import library

        match mode:
            case "library.player_update":
                return library.player_update(**parsed_params)
            case "library.status":
                return library.set_library_status(**parsed_params)
            case "library.clear_progress":
                return library.clear_progress(**parsed_params)
            case "library.dismiss_notification":
                return library.dismiss_notification(**parsed_params)
            case "library.watched_status":
                return library.mark_watched(**parsed_params)

    if "stremio" in mode:
        from apis.StremioAPI import stremio_api

        match mode:
            case "stremio.authenticate":
                return stremio_api.login()
            case "stremio.revoke_authentication":
                return stremio_api.logout()
