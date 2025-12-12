from __future__ import annotations

import dataclasses as dc
import ipaddress

import httpx
import ua_generator
from aiointel.http._types import UABrowsers, UADevices, UAOptions, UAPlatforms, UAVersionRanges



def _is_host_private_literal(host: str | None) -> bool:
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


class URLPolicyError(httpx.RequestError):
    """Raised when a request violates URLRestrictions."""
    pass


@dc.dataclass(slots=True, kw_only=True)
class URLRestrictions:
    force_https: bool = False
    reject_private_hosts: bool = False
    allowed_url_schemes: set[str] = dc.field(default_factory=set)

    def is_allowed_scheme(self, scheme: str) -> bool:
        s = scheme.lower()
        if s in {"https", "http"}:
            return True
        return s in self.allowed_url_schemes

    @property
    def allow_scheme_names(self) -> str:
        schemes = ["http", "https", *sorted(self.allowed_url_schemes)]
        return ", ".join(schemes)

    def get_url_violation(self, url: str | httpx.URL) -> str | None:
        u = httpx.URL(url) if isinstance(url, str) else url
        scheme = u.scheme.lower()

        if not self.is_allowed_scheme(scheme):
            return (
                f"URL scheme '{scheme}' is not allowed. "
                f"Allowed schemes: {self.allow_scheme_names}."
            )

        if self.reject_private_hosts and _is_host_private_literal(u.host):
            return f"URL host '{u.host}' is not allowed."

        return None

    async def __call__(self, request: httpx.Request) -> None:
        if self.force_https and request.url.scheme.lower() == "http":
            request.url = request.url.copy_with(scheme="https")

        if violation := self.get_url_violation(request.url):
            raise URLPolicyError(violation, request=request)


class UserAgentRandomizer:
    __slots__ = ('_generate_kwargs', '_overwrite', '_apply_extra_headers')

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


