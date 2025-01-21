from dataclasses import is_dataclass, fields

import xbmc
import xbmcgui
import xbmcvfs
from xbmcgui import Dialog

from addon import nas_addon


def parse_string(v):
    if isinstance(v, (int, float, bool, type(None))):
        return v

    match str(v).lower():
        case "none" | "null":
            return None
        case "true":
            return True
        case "false":
            return False
        case _:
            try:
                return int(v)
            except ValueError:
                try:
                    return float(v)
                except ValueError:
                    return v


def get_setting(setting):
    return parse_string(nas_addon.getSetting(setting))


def set_setting(setting, value):
    nas_addon.setSetting(setting, str(value))


def build_url(url_params, addon=None):
    from urllib.parse import urlencode

    return f"plugin://{addon or nas_addon.name}/?{urlencode(url_params)}"


def remove_keys(dict_item, dict_removals):
    for k in dict_removals:
        dict_item.pop(k, None)
    return dict_item


def append_path(_path):
    import sys

    sys.path.append(xbmcvfs.translatePath(_path))


def log(message: str, level: int = xbmc.LOGINFO):
    from sys import _getframe

    frame = _getframe(1)
    origin = (
        qualname
        if (qualname := frame.f_code.co_qualname) != "<module>"
        else f"{frame.f_code.co_filename.split(f'{nas_addon.name}/resources')[-1]}:{frame.f_lineno}"
    )

    xbmc.log(
        f"[ {nas_addon.name} | {origin} ]: {message}",
        level,
    )


def kodi_window():
    return xbmcgui.Window(10000)


def get_property(prop):
    return kodi_window().getProperty(prop)


def set_property(prop, value):
    return kodi_window().setProperty(prop, value)


def clear_property(prop):
    return kodi_window().clearProperty(prop)


def clear_all_properties():
    return kodi_window().clearProperties()


def external():
    return nas_addon.name not in xbmc.getInfoLabel("Container.PluginName")


def is_home():
    return xbmcgui.getCurrentWindowId() == 10000


def execute_built_in(command: str, params=None, block=False, build_only=False):
    if isinstance(params, dict):
        params = build_url(params)
    if params:
        command = command.format(params)
    if build_only:
        return command
    xbmc.executebuiltin(command, block)


def reload_skin():
    execute_built_in("ReloadSkin()")


def kodi_refresh():
    execute_built_in("UpdateLibrary(video,special://skin/foo)")


def show_busy_dialog():
    return execute_built_in("ActivateWindow(busydialognocancel)")


def hide_busy_dialog():
    execute_built_in("Dialog.Close(busydialognocancel)")
    execute_built_in("Dialog.Close(busydialog)")


def close_all_dialog():
    execute_built_in("Dialog.Close(all,true)")


def update_container(params, block=False, build_only=False):
    return execute_built_in("Container.Update({0})", params, block, build_only)


def run_plugin(params, block=False, build_only=False):
    return execute_built_in("RunPlugin({0})", params, block, build_only)


def container_refresh_input(params, block=False):
    return execute_built_in("Container.Refresh({0})", params, block)


def notification(line1, time=5000, icon=None):
    Dialog().notification("NAS", line1, icon or nas_addon.icon, time)


def timestamp_zone_format_switcher(timestamp: str) -> str:
    if timestamp.endswith("Z"):
        return f"{timestamp[:-1]}+00:00"
    elif timestamp.endswith("+00:00"):
        return f"{timestamp[:-6]}Z"
    log("Invalid timestamp passed, returning original")
    return timestamp


def dataclass_to_dict(obj) -> dict:
    def _convert(_obj):
        if is_dataclass(_obj):
            repr_fields = {
                f.name: getattr(_obj, f.name) for f in fields(_obj) if f.compare
            }
            return {k: _convert(v) for k, v in repr_fields.items()}
        elif isinstance(_obj, (list, tuple)):
            return [_convert(item) for item in _obj]
        elif isinstance(_obj, dict):
            return {k: _convert(v) for k, v in _obj.items()}
        return _obj

    return _convert(obj)
