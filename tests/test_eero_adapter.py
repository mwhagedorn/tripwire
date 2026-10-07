import asyncio
from typing import Any

import eero
import pytest

from tripwire.eero_adapter import AuthenticationError, EeroClientAdapter, RateLimitedError, TransportError, UnexpectedResponseError


class FakeEeroClient:
    def __init__(self, *, login_error: Exception | None = None) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.is_authenticated = False
        self.login_error = login_error

    async def __aenter__(self) -> "FakeEeroClient":
        self.calls.append(("__aenter__", None))
        return self

    async def __aexit__(self, *exc_info: Any) -> None:q
        self.calls.append(("__aexit__", None))

    async def login(self, user_identifier: str) -> bool:
        self.calls.append(("login", user_identifier))
        if self.login_error:
            raise self.login_error
        return True

    async def verify(self, verification_code: str) -> bool:
        self.calls.append(("verify", verification_code))
        self.is_authenticated = True
        return True

    async def logout(self) -> bool:
        self.calls.append(("logout", None))
        self.is_authenticated = False
        return True

    async def get_networks(self) -> dict[str, Any]:
        self.calls.append(("get_networks", None))
        return {"data": {"networks": []}}

    async def get_eeros(self, network_id: str) -> dict[str, Any]:
        self.calls.append(("get_eeros", network_id))
        return {"data": []}

    async def get_devices(self, network_id: str) -> dict[str, Any]:
        self.calls.append(("get_devices", network_id))
        return {"data": []}

    async def get_profiles(self, network_id: str) -> dict[str, Any]:
        self.calls.append(("get_profiles", network_id))
        return {"data": []}


def test_adapter_context_manager_delegates_to_underlying_client():
    fake = FakeEeroClient()
    adapter = EeroClientAdapter(client=fake)

    async def run():
        async with adapter:
            pass

    asyncio.run(run())

    assert fake.calls == [("__aenter__", None), ("__aexit__", None)]


def test_adapter_delegates_to_underlying_client():
    fake = FakeEeroClient()
    adapter = EeroClientAdapter(client=fake)

    async def run():
        assert await adapter.login("user@example.com") is True
        assert await adapter.verify("123456") is True
        assert adapter.is_authenticated is True
        assert await adapter.get_networks() == {"data": {"networks": []}}
        assert await adapter.get_eeros("net1") == {"data": []}
        assert await adapter.get_devices("net1") == {"data": []}
        assert await adapter.get_profiles("net1") == {"data": []}
        assert await adapter.logout() is True
        assert adapter.is_authenticated is False

    asyncio.run(run())

    assert fake.calls == [
        ("login", "user@example.com"),
        ("verify", "123456"),
        ("get_networks", None),
        ("get_eeros", "net1"),
        ("get_devices", "net1"),
        ("get_profiles", "net1"),
        ("logout", None),
    ]


@pytest.mark.parametrize("eero_error,adapter_error", [
    (eero.EeroAuthenticationException("bad code"), AuthenticationError),
    (eero.EeroAccessDeniedException(403, "denied"), AuthenticationError),
    (eero.EeroClientBlockedException(403, "blocked"), AuthenticationError),
    (eero.EeroRateLimitException("slow down"), RateLimitedError),
    (eero.EeroNetworkException("offline"), TransportError),
    (eero.EeroTimeoutException("timed out"), TransportError),
    (eero.EeroValidationException("field", "bad shape"), UnexpectedResponseError),
])
def test_adapter_translates_eero_exceptions(eero_error, adapter_error):
    fake = FakeEeroClient(login_error=eero_error)
    adapter = EeroClientAdapter(client=fake)

    with pytest.raises(adapter_error):
        asyncio.run(adapter.login("user@example.com"))
