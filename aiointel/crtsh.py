import asyncio
from collections.abc import Iterator
import dataclasses as dc

import httpx

from aiointel._model import DataclassMixin
from aiointel.http import AiointelBaseClient, httpx_retry



@dc.dataclass(frozen=True)
class CertshResult(DataclassMixin):
    domain: str
    total: int
    subdomains: set[str]



def _normalize_hostname(hostname: str) -> str:
    return hostname.strip().lower().rstrip('.')

def _iter_name_values(name_value: str, domain: str) -> Iterator[str]:
    for line in str(name_value).splitlines():
        hostname = _normalize_hostname(line)
        if hostname and hostname != domain:
            yield hostname

def _walk_certsh_response(data: list[dict], domain: str) -> Iterator[str]:
    for entry in data:
        if name_value := entry.get('name_value'):
            yield from _iter_name_values(name_value, domain)

        elif common_name := entry.get('common_name'):
            hostname = _normalize_hostname(common_name)
            if hostname and hostname != domain:
                yield hostname


@httpx_retry()
async def _fetch_crtsh_domain(
    client: httpx.AsyncClient,
    domain: str,
    url: str
) -> list[dict]:
    '''
    Fetch certificate data for a domain from cert.sh.

    Parameters
    ----------
    client : httpx.AsyncClient
        The HTTP client to use for the request.
    domain : str
        The domain to fetch certificate data for.

    Returns
    -------
    list[dict]
        The JSON response from cert.sh.
    '''
    params = {
        'q': f'%.{domain}',
        'output': 'json',
    }

    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()



class CrtshClient(AiointelBaseClient):
    base_url: str = 'https://crt.sh/'

    async def fetch(self, domain: str) -> list[dict]:
        return await _fetch_crtsh_domain(
            client=self._client,
            domain=domain,
            url=self.base_url
        )

    async def fetch_subdomains(self, domain: str) -> CertshResult:
        data = await self.fetch(domain)
        subdomains = set(_walk_certsh_response(data, domain))
        return CertshResult(
            domain=domain,
            total=len(subdomains),
            subdomains=subdomains,
        )

    async def gather_subdomains(self, *domains: str) -> dict[str, CertshResult]:
        tasks = [
            self.fetch_subdomains(domain)
            for domain in domains
        ]
        results = await asyncio.gather(*tasks)
        return {result.domain: result for result in results}


