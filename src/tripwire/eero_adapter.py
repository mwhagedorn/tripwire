"""Adapter boundary between tripwire and the unofficial `eero` client library.

Scanner and CLI code depend on `EeroAdapter` and the error types below, never
on `eero.EeroClient` or `eero.EeroException` directly, so a future client
swap only touches this module.
"""

from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable, Protocol, TypeVar

import eero


class AdapterError(Exception):
    """Base for every error raised through the `EeroAdapter` boundary."""


class AuthenticationError(AdapterError):
    """Login, verification, or the stored session was rejected."""


class RateLimitedError(AdapterError):
    """The Eero API rejected the request for making too many of them."""


class TransportError(AdapterError):
    """A network-level failure occurred talking to the Eero API."""


class UnexpectedResponseError(AdapterError):
    """The Eero API returned a response the adapter did not expect."""


def _translate(exc: eero.EeroException) -> AdapterError:
    if isinstance(
        exc,
        (eero.EeroAuthenticationException, eero.EeroAccessDeniedException, eero.EeroClientBlockedException),
    ):
        return AuthenticationError(str(exc))
    if isinstance(exc, eero.EeroRateLimitException):
        return RateLimitedError(str(exc))
    if isinstance(exc, (eero.EeroNetworkException, eero.EeroTimeoutException)):
        return TransportError(str(exc))
    return UnexpectedResponseError(str(exc))


_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def _translating_eero_errors(func: _F) -> _F:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except eero.EeroException as exc:
            raise _translate(exc) from exc

    return wrapper  # type: ignore[return-value]


class EeroAdapter(Protocol):
    """Raw Eero network access that the rest of tripwire depends on.

    Every method raises only `AdapterError` subclasses on failure, never a
    `eero.EeroException`.
    """

    async def __aenter__(self) -> "EeroAdapter": ...

    async def __aexit__(self, *exc_info: Any) -> None: ...

    async def login(self, user_identifier: str) -> bool: ...

    async def verify(self, verification_code: str) -> bool: ...

    async def logout(self) -> bool: ...

    @property
    def is_authenticated(self) -> bool: ...

    async def get_networks(self) -> dict[str, Any]: ...

    async def get_eeros(self, network_id: str) -> dict[str, Any]: ...

    async def get_devices(self, network_id: str) -> dict[str, Any]: ...

    async def get_profiles(self, network_id: str) -> dict[str, Any]: ...


class EeroClientAdapter:
    """Adapts `eero.EeroClient` to the `EeroAdapter` interface.

    Methods forward to the underlying client and return its raw response
    envelopes unchanged; normalizing those into tripwire's snapshot model
    is the scanner's job, not the adapter's. Any `eero.EeroException` the
    client raises is translated to an `AdapterError` before it reaches the
    caller.
    """

    def __init__(self, client: eero.EeroClient | None = None, cookie_file: str | None = None) -> None:
        self._client = client if client is not None else eero.EeroClient(cookie_file=cookie_file)

    async def __aenter__(self) -> "EeroClientAdapter":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._client.__aexit__(*exc_info)

    @_translating_eero_errors
    async def login(self, user_identifier: str) -> bool:
        return await self._client.login(user_identifier)

    @_translating_eero_errors
    async def verify(self, verification_code: str) -> bool:
        return await self._client.verify(verification_code)

    @_translating_eero_errors
    async def logout(self) -> bool:
        return await self._client.logout()

    @property
    def is_authenticated(self) -> bool:
        return self._client.is_authenticated

    @_translating_eero_errors
    async def get_networks(self) -> dict[str, Any]:
        return await self._client.get_networks()

    @_translating_eero_errors
    async def get_eeros(self, network_id: str) -> dict[str, Any]:
        return await self._client.get_eeros(network_id)

    @_translating_eero_errors
    async def get_devices(self, network_id: str) -> dict[str, Any]:
        return await self._client.get_devices(network_id)

    @_translating_eero_errors
    async def get_profiles(self, network_id: str) -> dict[str, Any]:
        return await self._client.get_profiles(network_id)
