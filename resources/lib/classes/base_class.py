from __future__ import annotations

from abc import ABCMeta
from datetime import datetime, timezone
from typing import Any, get_type_hints, get_args, get_origin

from modules.utils import filter_dict


class StremioObjectMeta(ABCMeta):
    def __call__(cls, *args, **kwargs):
        if not issubclass(cls, StremioObject):
            raise TypeError("Class is not a StremioObject")
        kwargs = cls.transform_dict(kwargs)
        return super().__call__(*args, **kwargs)


class StremioObject(metaclass=StremioObjectMeta):
    @classmethod
    def transform_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        def _build_cls(classes: set[type], val):
            for _cls in classes:
                try:
                    if isinstance(val, dict):
                        return _cls(**val)
                    if isinstance(val, tuple):
                        return _cls(*val)

                    if _cls == datetime:
                        return datetime.fromisoformat(
                            val.replace("Z", "+00:00")
                        ).astimezone(timezone.utc)

                    return _cls(val)
                except TypeError:
                    pass

        data = filter_dict(cls, data)
        type_hints = get_type_hints(cls)
        for key, value in data.items():
            val_type = type_hints.get(key)

            if get_origin(val_type) is list:
                if not isinstance(value, list):
                    value = [value]
                args = set(get_args(val_type))
                for idx, item in enumerate(value):
                    if type(item) in args:
                        continue
                    value[idx] = _build_cls(args, item)
                continue

            types: set[type] = {val_type, *get_args(val_type)}
            if type(value) not in types:
                data[key] = _build_cls(types, value)
        return data

    def as_dict(self) -> dict:
        from dataclasses import fields, is_dataclass

        def _convert(_obj):
            if is_dataclass(_obj):
                init_fields = {
                    f.name: getattr(_obj, f.name) for f in fields(_obj) if f.init
                }
                return {k: _convert(v) for k, v in init_fields.items()}
            if isinstance(_obj, (list, tuple, set)):
                return [_convert(item) for item in _obj]
            if isinstance(_obj, dict):
                return {k: _convert(v) for k, v in _obj.items()}
            if isinstance(_obj, datetime):
                return _obj.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            return _obj

        return _convert(self)
