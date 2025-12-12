from __future__ import annotations

import dataclasses as dc
from typing import Self

import httpx
import ua_generator

from aiointel.http._types import (
    HeaderProfile,
    UABrowsers,
    UADevices,
    UAOptions,
    UAPlatforms,
    UAVersionRanges,
)


class UserAgentRandomizer:
    __slots__ = ('_apply_extra_headers', '_generate_kwargs', '_overwrite')

    def __init__(
        self,
        *,
        platforms: UAPlatforms | None = None,
        browsers: UABrowsers | None = None,
        devices: UADevices | None = None,
        version_ranges: dict[str, UAVersionRanges] | None = None,
        tied_safari_version: bool = False,
        weighted_versions: bool = False,
        overwrite: bool = False,
        apply_extra_headers: bool = True,
    ) -> None:
        ua_generator_options = UAOptions(
            weighted_versions=weighted_versions,
            version_ranges=version_ranges,
        )
        ua_generator_options.tied_safari_version = tied_safari_version
        self._generate_kwargs = {
            'platforms': platforms,
            'browsers': browsers,
            'devices': devices,
            'options': ua_generator_options,
        }
        self._overwrite = overwrite
        self._apply_extra_headers = apply_extra_headers

    def generate_headers(self) -> dict[str, str]:
        ua_instance = ua_generator.generate(**self._generate_kwargs)
        return dict(ua_instance.headers.get())

    async def __call__(self, request: httpx.Request) -> None:
        headers = self.generate_headers()

        if user_agent := headers.get('user-agent'):
            if self._overwrite or 'user-agent' not in request.headers:
                request.headers['user-agent'] = user_agent

        if self._apply_extra_headers:
            for key, value in headers.items():
                if key.lower() != 'user-agent':
                    request.headers.setdefault(key, value)


@dc.dataclass(slots=True)
class BrowserHeaderOptions:
    profile: HeaderProfile = 'nav'
    accept_language: str = 'en-US,en;q=0.9'
    accept_encoding: str = 'gzip, deflate, br'
    dnt: bool = False
    upgrade_insecure_requests: bool = True
    include_fetch_metadata: bool = False
    overwrite_existing: bool = False

    @property
    def accept_header_value(self) -> str:
        if self.profile == 'nav':
            return (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            )
        return "application/json, text/javascript, */*"

    @property
    def metadata_headers(self) -> dict[str, str]:
        if self.profile == 'nav':
            return {
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
            }
        return {
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }

    def get_headers(self) -> dict[str, str]:
        headers = {
            'accept-language': self.accept_language,
            'accept-encoding': self.accept_encoding,
            'accept': self.accept_header_value,
            **self.metadata_headers
        }
        if self.dnt:
            headers['dnt'] = '1'

        if self.upgrade_insecure_requests:
            headers['upgrade-insecure-requests'] = '1'

        return headers


class BrowserHeaders(httpx.Headers):
    @classmethod
    def defaults(cls, *, options: BrowserHeaderOptions | None = None) -> Self:
        options = options or BrowserHeaderOptions()
        headers = options.get_headers()
        return cls(headers)

    def merge(
        self,
        other: httpx.Headers | dict[str, str],
        *,
        overwrite: bool = False,
    ) -> Self:
        if not other:
            return self

        out = self.copy()
        if overwrite:
            out.update(other)
            return type(self)(out)

        for k, v in other.items():
            out.setdefault(k, v)

        return type(self)(out)

    def apply_to(
        self,
        request: httpx.Request,
        *,
        overwrite: bool = False,
    ) -> None:
        if overwrite:
            request.headers.update(self)
            return

        for k, v in self.items():
            request.headers.setdefault(k, v)
