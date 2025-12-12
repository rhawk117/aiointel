from collections.abc import Awaitable, Callable
import functools
import random
import httpcore
import asyncio
from typing import ParamSpec, TypeVar

import httpx

from aiointel.http._exceptions import URLPolicyError


P = ParamSpec('P')
R = TypeVar('R')

_HTTPX_ERRORS = (
    ConnectionError,
    asyncio.TimeoutError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
    httpx.ProxyError,
    httpx.NetworkError,
    httpcore.ConnectError,
)

class RetryPolicy:

    def __init__(
        self,
        *,
        attempts: int = 3,
        delay: float = 0.25,
        jitter: float = 0.1,
    ) -> None:
        '''
        Parameters
        ----------
        attempts : int, optional
            The maximum number of attempts, by default 3
        delay : float, optional
            The base delay between attempts, by default 0.25
        jitter : float, optional
            The jitter factor to apply to the delay, by default 0.1
        '''
        self.attempts: int = attempts
        self.delay: float = delay
        self.jitter: float = jitter
        self.httpx_errors = _HTTPX_ERRORS

    def get_timeout(self, attempt_no: int) -> float:
        base = self.delay * attempt_no

        if self.jitter:
            j = base * self.jitter
            base += random.uniform(-j, j)

        return max(0.0, base)

    @property
    def attempt_range(self) -> range:
        return range(1, self.attempts + 1)


def httpx_retry(
    *,
    attempts: int = 3,
    delay: float = 0.25,
    jitter: float = 0.1,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    policy = RetryPolicy(
        attempts=attempts,
        delay=delay,
        jitter=jitter,
    )

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal policy
            last_exception: Exception | None = None

            for attempt_no in policy.attempt_range:
                try:
                    return await func(*args, **kwargs)
                except policy.httpx_errors as exc:
                    last_exception = exc
                    if attempt_no == policy.attempts or exc is URLPolicyError:
                        break

                    timeout = policy.get_timeout(attempt_no)
                    await asyncio.sleep(timeout)
                except Exception as exc:
                    raise exc

            raise last_exception  # type: ignore

        return wrapper

    return decorator