from typing import TypeVar, Any
from urllib.parse import parse_qsl

from indexers.base_indexer import BaseIndexer
from indexers.navigator import Navigator
from modules.utils import external, log, parse_string, filter_dict

T = TypeVar("T")


def build_class(cls: type[T], data: dict[str, Any]) -> T:
    return cls(**filter_dict(cls, data))


def sys_exit_check():
    return external()


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

        case "playback":
            match func:
                case "media":
                    from modules.sources import Sources

                    return build_class(Sources, params).play(
                        sys.argv[3] == "resume:true"
                    )

        case "indexer":
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
                case "relations":
                    from indexers.relations import Relations

                    selected_class = Relations

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
