from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any,  Protocol, TypeVar, TypedDict, runtime_checkable, cast

import httpx
from ua_generator.options import Options
from ua_generator.data import T_BROWSERS, T_PLATFORMS, T_DEVICES
from ua_generator.data.version import VersionRange


HookCallable = Callable[[Any], Awaitable[None]]
RequestCallable = Callable[[httpx.Request], Awaitable[None]]
ResponseCallable = Callable[[httpx.Response], Awaitable[None]]


@runtime_checkable
class RequestHook(Protocol):
    async def __call__(self, request: httpx.Request) -> None: ...


@runtime_checkable
class ResponseHook(Protocol):
    async def __call__(self, response: httpx.Response) -> None: ...


@runtime_checkable
class ClientMiddleware(Protocol):
    async def on_request(self, request: httpx.Request) -> None: ...
    async def on_response(self, response: httpx.Response) -> None: ...


# These are type aliases so users don't have to import VersionRange/Options directly.
UAVersionRanges = VersionRange
UAOptions = Options

UAPlatforms = T_PLATFORMS | tuple[T_PLATFORMS, ...] | list[T_PLATFORMS]
UABrowsers = T_BROWSERS | tuple[T_BROWSERS, ...] | list[T_BROWSERS]
UADevices = T_DEVICES | tuple[T_DEVICES, ...] | list[T_DEVICES]


