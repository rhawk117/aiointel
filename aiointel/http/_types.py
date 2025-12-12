from __future__ import annotations

import ssl
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol, TypedDict

import httpx
from ua_generator.data import T_BROWSERS, T_DEVICES, T_PLATFORMS
from ua_generator.data.version import VersionRange
from ua_generator.options import Options

HookCallable = Callable[[Any], Awaitable[None]]
RequestCallable = Callable[[httpx.Request], Awaitable[None]]
ResponseCallable = Callable[[httpx.Response], Awaitable[None]]


class RequestHook(Protocol):
    async def __call__(self, request: httpx.Request) -> None: ...


class ResponseHook(Protocol):
    async def __call__(self, response: httpx.Response) -> None: ...


class ClientTimeouts(TypedDict, total=False):
    connect: float
    read: float
    write: float
    pool: float


class Middleware(TypedDict, total=False):
    request: list[RequestHook]
    response: list[ResponseHook]


class TransportLimits(TypedDict, total=False):
    max_connections: int
    max_keepalive_connections: int
    keepalive_expiry: float


class TransportSocketOptions(TypedDict, total=False):
    nodelay: bool
    enable_keepalive: bool
    keepalive_idle: int
    keepalive_count: int
    user_timeout_ms: int


# these are type aliases so users don't have to import VersionRange/Options directly.
UAVersionRanges = VersionRange
UAOptions = Options

UAPlatforms = T_PLATFORMS | tuple[T_PLATFORMS, ...] | list[T_PLATFORMS]
UABrowsers = T_BROWSERS | tuple[T_BROWSERS, ...] | list[T_BROWSERS]
UADevices = T_DEVICES | tuple[T_DEVICES, ...] | list[T_DEVICES]
HeaderProfile = Literal['nav', 'xhr', 'fetch']

VerifyType = bool | str | ssl.SSLContext
CertTypes = str | tuple[str, str] | tuple[str, str, str]
SocketOption = tuple[int, int, int]
