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
    params = {
        k: parse_string(v)
        for k, v in dict(parse_qsl(sys.argv[2][1:], keep_blank_values=True)).items()
    }

    mode = params.get("mode", "navigator")
    func = params.get("func", "main")

    if params.get("mode", None):
        del params["mode"]
    if params.get("func", None):
        del params["func"]

    match mode:
        case "navigator":
            navigator = build_class(Navigator, params)

            match func:
                case "main":
                    return navigator.main()
                case "home":
                    return navigator.home()
                case "discover":
                    return navigator.discover()
                case "library":
                    return navigator.library()
                case "search":
                    return navigator.search()
                case "settings":
                    return navigator.settings()

        case "playback":
            match func:
                case "media":
                    from modules.sources import Sources

                    return build_class(Sources, params).play()

        case "build":
            if "refreshed" not in params:
                params["refreshed"] = False

            selected_class: type[BaseIndexer] | None = None
            match func:
                case "catalog":
                    from indexers.catalog import Catalog

                    selected_class = Catalog
                case "discover":
                    from indexers.discover import Discover

                    selected_class = Discover
                case "seasons":
                    from indexers.seasons import Seasons

                    selected_class = Seasons
                case "episodes":
                    from indexers.episodes import Episodes

                    selected_class = Episodes

            return build_class(selected_class, params) if selected_class else None

        case "library":
            from modules import library

            match func:
                case "player_update":
                    return library.player_update(**params)
                case "status":
                    return library.set_library_status(**params)
                case "clear_progress":
                    return library.clear_progress(**params)
                case "dismiss_notification":
                    return library.dismiss_notification(**params)
                case "watched_status":
                    return library.mark_watched(**params)

        case "stremio":
            from apis.StremioAPI import stremio_api

            match func:
                case "authenticate":
                    return stremio_api.login()
                case "revoke_authentication":
                    return stremio_api.logout()
