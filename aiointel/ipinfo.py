import asyncio
import dataclasses as dc

import httpx

from aiointel.crtsh import DataclassMixin
from aiointel.http import AiointelBaseClient, httpx_retry



@dc.dataclass(frozen=True)
class IPInfoModel(DataclassMixin):
    ip: str
    city: str | None = None
    country: str | None = None
    postal: str | None = None
    org: str | None = None
    location: str | None = None
    timezone: str | None = None
    extras: dict = dc.field(default_factory=dict)

    @property
    def maps_url(self) -> str | None:
        if self.location:
            return f'https://www.google.com/maps/search/?q{self.location}'
        return None


@httpx_retry()
async def _fetch_ipinfo_json(
    client: httpx.AsyncClient,
    ip_address: str,
) -> dict:
    '''
    Fetch IP information from ipinfo.io.

    Parameters
    ----------
    client : httpx.AsyncClient
        The HTTP client to use for the request.
    ip_address : str
        The IP address to fetch information for.

    Returns
    -------
    dict
        The JSON response from ipinfo.io.
    '''
    response = await client.get(f'/{ip_address}/json')
    response.raise_for_status()
    return response.json()


class IPInfoClient(AiointelBaseClient):
    base_url = 'https://ipinfo.io'

    async def fetch(self, ip_address: str) -> dict:
        '''
        Fetch IP information from ipinfo.io.

        Parameters
        ----------
        ip_address : str
            The IP address to fetch information for.

        Returns
        -------
        dict
            The JSON response from ipinfo.io.
        '''
        return await _fetch_ipinfo_json(self._client, ip_address)

    async def fetch_info(self, ip_address: str) -> IPInfoModel:
        response = await self.fetch(ip_address)
        if response.get('bogon'):
            raise ValueError(f'IP address `{ip_address}` is a bogon.')

        model_init = {
            'ip': ip_address,
            'extras': {},
        }
        model_fields = set(IPInfoModel.get_field_names())
        for key, value in response.items():
            if key in model_fields:
                model_init[key] = value
            else:
                model_init['extras'][key] = value

        return IPInfoModel(**model_init)

    async def gather_info(self, *ip_addresses: str) -> dict[str, IPInfoModel]:
        tasks = [
            self.fetch_info(ip_address)
            for ip_address in ip_addresses
        ]
        results = await asyncio.gather(*tasks)
        return {result.ip: result for result in results}
