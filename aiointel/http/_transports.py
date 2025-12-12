# aiointel/http/_transports.py
import dataclasses as dc
import ipaddress
import socket

import httpx

from aiointel.http._types import (
    CertTypes,
    SocketOption,
    TransportLimits,
    TransportSocketOptions,
    VerifyType,
)
from aiointel.http._exceptions import URLPolicyError



def is_host_private_literal(host: str | None) -> bool:
    if not host:
        return False

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
    )


def build_socket_options(options: TransportSocketOptions | None) -> list[SocketOption]:
    options = options or {}
    socket_options: list[SocketOption] = []

    if options.get('nodelay') and hasattr(socket, 'TCP_NODELAY'):
        socket_options.append((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1))

    if options.get('enable_keepalive'):
        socket_options.append((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1))

    idle = options.get('keepalive_idle')
    if idle is not None:
        if hasattr(socket, 'TCP_KEEPIDLE'):
            socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, int(idle)))
        elif hasattr(socket, 'TCP_KEEPALIVE'):  # macOS
            socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, int(idle)))  # type: ignore[arg-type]

    interval = options.get('keepalive_interval')
    if interval is not None and hasattr(socket, 'TCP_KEEPINTVL'):
        socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, int(interval)))

    count = options.get('keepalive_count')
    if count is not None and hasattr(socket, 'TCP_KEEPCNT'):
        socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPCNT, int(count)))

    user_timeout = options.get('user_timeout_ms')
    if user_timeout is not None and hasattr(socket, 'TCP_USER_TIMEOUT'):
        socket_options.append((socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, int(user_timeout)))  # type: ignore[arg-type]

    return socket_options


def _DEFAULT_LIMITS() -> TransportLimits:
    return TransportLimits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=15.0,
    )


@dc.dataclass(slots=True, kw_only=True)
class TransportOptions:
    '''
    Options for constructing an async transport with sane defaults.

    Default behavior:
      - Uses httpx.AsyncHTTPTransport (supported/stable)
      - Enables HTTP/1.1 always, optionally enables HTTP/2 via http2=True

    Advanced behavior:
      - If you set socket-level flags (keepalive/nodelay/user-timeout),
        we switch to a small custom AsyncBaseTransport backed by httpcore.AsyncConnectionPool
        because httpcore exposes `socket_options`. :contentReference[oaicite:3]{index=3}
    '''

    limits: TransportLimits = dc.field(default_factory=_DEFAULT_LIMITS)
    verify: VerifyType = True
    cert: CertTypes | None = None
    trust_env: bool = True
    http2: bool = False
    retries: int = 0
    local_address: str | None = None
    uds: str | None = None
    proxy: str | httpx.Proxy | None = None
    socket: TransportSocketOptions = dc.field(default_factory=TransportSocketOptions)

    def update(
        self,
        *,
        socket: TransportSocketOptions | None = None,
        limits: TransportLimits | None = None,
    ) -> None:
        if socket is not None:
            self.socket.update(socket)

        if limits is not None:
            self.limits.update(limits)

    @property
    def use_custom_socket_options(self) -> bool:
        return any(self.socket.values())


@dc.dataclass(slots=True, kw_only=True)
class URLRestrictions:
    force_https: bool = False
    reject_private_hosts: bool = False
    allowed_url_schemes: set[str] = dc.field(default_factory=set)

    def is_allowed_scheme(self, scheme: str) -> bool:
        s = scheme.lower()
        if s in {'https', 'http'}:
            return True
        return s in self.allowed_url_schemes

    def _scheme_violation(self, scheme: str) -> str | None:
        allowed_schemes = ['http', 'https', *self.allowed_url_schemes]
        return (
            f'URL scheme `{scheme}` is not allowed one of the allowed schemes '
            f'which are: {', '.join(allowed_schemes)}.'
        )

    def get_url_violation(self, url: str | httpx.URL) -> str | None:
        u = httpx.URL(url) if isinstance(url, str) else url
        scheme = u.scheme.lower()

        if not self.is_allowed_scheme(scheme):
            return self._scheme_violation(scheme)

        if self.reject_private_hosts and is_host_private_literal(u.host):
            return f'URL host `{u.host}` is not allowed.'

        return None

    async def enforce(self, request: httpx.Request) -> None:
        if self.force_https and request.url.scheme.lower() == 'http':
            request.url = request.url.copy_with(scheme='https')

        if violation := self.get_url_violation(request.url):
            raise URLPolicyError(violation, request=request)


class URLSafeAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        *,
        restrictions: URLRestrictions,
        inner: httpx.AsyncBaseTransport,
    ) -> None:
        self._inner = inner
        self._restrictions = restrictions

    async def handle_async_request(
        self,
        request: httpx.Request
    ) -> httpx.Response:
        await self._restrictions.enforce(request)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def create_async_transport(
    *,
    options: TransportOptions | None = None,
    url_restrictions: URLRestrictions | None = None,
) -> httpx.AsyncBaseTransport:
    options = options or TransportOptions()
    socket_options = build_socket_options(options.socket) if options.use_custom_socket_options else None
    base_transport = httpx.AsyncHTTPTransport(
        verify=options.verify,
        cert=options.cert,
        trust_env=options.trust_env,
        http2=options.http2,
        limits=httpx.Limits(**options.limits),
        local_address=options.local_address,
        uds=options.uds,
        proxy=options.proxy,
        socket_options=socket_options,
        retries=options.retries,
    )
    if url_restrictions:
        return URLSafeAsyncTransport(
            restrictions=url_restrictions,
            inner=base_transport
        )

    return base_transport
