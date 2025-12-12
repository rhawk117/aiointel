from __future__ import annotations

import dataclasses as dc
import functools
from typing import Any, ClassVar, Self, cast


@functools.lru_cache
def _fields_for(cls: type) -> tuple[dc.Field[Any], ...]:
    if not dc.is_dataclass(cls):
        raise TypeError(f'{cls.__name__} must be a dataclass to use ModelMixin.')
    return cast('tuple[dc.Field[Any], ...]', dc.fields(cls))


def _is_dc_instance(obj: object) -> bool:
    return dc.is_dataclass(obj) and not isinstance(obj, type)


def _convert_model(obj: Any, *, recurse: bool) -> Any:
    if recurse and _is_dc_instance(obj):
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            return obj.to_dict(recurse=True)  # type: ignore[attr-defined]

        cls = type(obj)
        return {
            f.name: _convert_model(getattr(obj, f.name), recurse=True)
            for f in _fields_for(cls)
        }

    if recurse and isinstance(obj, dict):
        return {k: _convert_model(v, recurse=True) for k, v in obj.items()}

    if recurse and isinstance(obj, tuple):
        return tuple(_convert_model(v, recurse=True) for v in obj)

    if recurse and isinstance(obj, list):
        return [_convert_model(v, recurse=True) for v in obj]

    if recurse and isinstance(obj, set):
        return {_convert_model(v, recurse=True) for v in obj}

    return obj


class DataclassMixin:
    __slots__: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def get_fields(cls) -> tuple[dc.Field[Any], ...]:
        return _fields_for(cls)

    @classmethod
    def get_field_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in _fields_for(cls))

    def to_tuple(self) -> tuple[Any, ...]:
        cls = type(self)
        return tuple(getattr(self, f.name) for f in _fields_for(cls))

    def to_dict(
        self,
        *,
        recurse: bool = True,
        exclude_none: bool = False,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cls = type(self)
        out: dict[str, Any] = {}

        for f in _fields_for(cls):
            val = getattr(self, f.name)
            if exclude_none and val is None:
                continue
            out[f.name] = _convert_model(val, recurse=recurse)

        if extras:
            out.update(extras)

        return out

    def copy_with(self, **updates: Any) -> Self:
        cls = type(self)
        names = {f.name for f in _fields_for(cls)}
        unknown = [k for k in updates.keys() if k not in names]
        if unknown:
            raise TypeError(
                f'{cls.__name__}.copy_with got unknown field(s): {", ".join(unknown)}'
            )
        return dc.replace(self, **updates)  # type: ignore[arg-type]

    def as_string(
        self,
        *,
        multiline: bool = False,
        indent: int = 2,
        include_none: bool = True,
        max_value_len: int | None = None,
    ) -> str:
        cls = type(self)
        items: list[tuple[str, Any]] = []
        for f in _fields_for(cls):
            v = getattr(self, f.name)
            if (v is None) and (not include_none):
                continue
            items.append((f.name, v))

        def _fmt(v: Any) -> str:
            s = repr(v)
            if max_value_len is not None and len(s) > max_value_len:
                return s[: max_value_len - 1] + '…'
            return s

        if not multiline:
            body = ', '.join(f'{k}={_fmt(v)}' for k, v in items)
            return f'{cls.__name__}({body})'

        pad = ' ' * indent
        body = '\n'.join(f'{pad}{k}={_fmt(v)},' for k, v in items)
        return f'{cls.__name__}(\n{body}\n)'
