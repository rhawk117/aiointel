# aiointel/http/_client.py
import dataclasses as dc
from typing import Any

import httpx

from aiointel.http._headers import (
    BrowserHeaderOptions,
    BrowserHeaders,
    UserAgentRandomizer,
)
from aiointel.http._transports import (
    TransportOptions,
    URLRestrictions,
    URLSafeAsyncTransport,
    create_async_transport,
)
from aiointel.http._types import ClientTimeouts, Middleware


@dc.dataclass(slots=True)
class ClientOptions:
    base_url: httpx.URL | str = ''
    auth: httpx.Auth | None = None
    follow_redirects: bool = False
    max_redirects: int = 20
    timeouts: ClientTimeouts | None = None
    params: httpx.QueryParams | dict[str, str] = dc.field(default_factory=httpx.QueryParams)
    headers: httpx.Headers = dc.field(default_factory=httpx.Headers)
    cookies: httpx.Cookies = dc.field(default_factory=httpx.Cookies)
    mounts: dict[str, httpx.AsyncBaseTransport] = dc.field(default_factory=dict)

    def set_timeouts(self, value: float) -> None:
        self.timeouts = self.timeouts or {}
        self.timeouts.update({
            'connect': value,
            'read': value,
            'write': value,
            'pool': value,
        })

    def __post_init__(self) -> None:
        if not self.timeouts:
            self.set_timeouts(5.0)

    def use_browser_headers(
        self,
        *,
        options: BrowserHeaderOptions | None = None,
    ) -> None:
        headers = BrowserHeaders.defaults(options=options)
        self.headers = headers.merge(self.headers)

    def to_kwargs(self) -> dict[str, Any]:
        return {
            'base_url': self.base_url,
            'auth': self.auth,
            'follow_redirects': self.follow_redirects,
            'max_redirects': self.max_redirects,
            'timeout': httpx.Timeout(**self.timeouts or {}),
            'params': self.params,
            'headers': self.headers,
            'cookies': self.cookies,
            'mounts': self.mounts,
        }


def create_async_client(
    *,
    client_options: ClientOptions | None = None,
    user_agent_randomizer: UserAgentRandomizer | bool = False,
    transport_options: TransportOptions | None = None,
    url_restrictions: URLRestrictions | None = None,
    middleware: Middleware | None = None,
    custom_transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    client_options = client_options or ClientOptions()

    middleware = middleware or {}
    middleware.setdefault('request', [])
    middleware.setdefault('response', [])

    if user_agent_randomizer is not False:
        if user_agent_randomizer is True:
            user_agent_randomize = UserAgentRandomizer()
        middleware['request'].append(user_agent_randomize)  # type: ignore[arg-type]

    if custom_transport:
        transport = custom_transport
        if url_restrictions:
            transport = URLSafeAsyncTransport(
                restrictions=url_restrictions,
                inner=custom_transport,
            )
    else:
        transport = create_async_transport(
            options=transport_options,
            url_restrictions=url_restrictions,
        )

    return httpx.AsyncClient(
        **client_options.to_kwargs(),
        transport=transport,
        event_hooks=middleware,  # type: ignore[arg-type]
    )
