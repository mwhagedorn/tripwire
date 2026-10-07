import asyncio

from tripwire.cli import _confirm_code, _end_session, _request_code
from tripwire.eero_adapter import AuthenticationError, RateLimitedError, TransportError


class FakeAdapter:
    def __init__(
        self,
        *,
        login_result=True,
        login_error=None,
        verify_result=True,
        verify_error=None,
        logout_result=True,
        logout_error=None,
    ):
        self.login_result = login_result
        self.login_error = login_error
        self.verify_result = verify_result
        self.verify_error = verify_error
        self.logout_result = logout_result
        self.logout_error = logout_error
        self.calls: list[tuple[str, str]] = []

    async def __aenter__(self) -> "FakeAdapter":
        return self

    async def __aexit__(self, *exc_info) -> None:
        pass

    async def login(self, identifier: str) -> bool:
        self.calls.append(("login", identifier))
        if self.login_error:
            raise self.login_error
        return self.login_result

    async def logout(self) -> bool:
        self.calls.append(("logout", ""))
        if self.logout_error:
            raise self.logout_error
        return self.logout_result

    async def verify(self, code: str) -> bool:
        self.calls.append(("verify", code))
        if self.verify_error:
            raise self.verify_error
        return self.verify_result


def test_request_code_calls_adapter_login():
    adapter = FakeAdapter()
    result = asyncio.run(_request_code(adapter, "user@example.com"))
    assert result is True
    assert adapter.calls == [("login", "user@example.com")]


def test_request_code_propagates_adapter_errors():
    adapter = FakeAdapter(login_error=RateLimitedError("too many requests"))
    try:
        asyncio.run(_request_code(adapter, "user@example.com"))
        assert False, "expected RateLimitedError"
    except RateLimitedError:
        pass


def test_confirm_code_calls_adapter_verify():
    adapter = FakeAdapter()
    result = asyncio.run(_confirm_code(adapter, "123456"))
    assert result is True
    assert adapter.calls == [("verify", "123456")]


def test_confirm_code_returns_false_on_rejected_code():
    adapter = FakeAdapter(verify_result=False)
    result = asyncio.run(_confirm_code(adapter, "000000"))
    assert result is False


def test_end_session_calls_adapter_logout():
    adapter = FakeAdapter()
    result = asyncio.run(_end_session(adapter))
    assert result is True
    assert adapter.calls == [("logout", "")]


def test_end_session_propagates_adapter_errors():
    adapter = FakeAdapter(logout_error=TransportError("offline"))
    try:
        asyncio.run(_end_session(adapter))
        assert False, "expected TransportError"
    except TransportError:
        pass


def test_confirm_code_propagates_adapter_errors():
    adapter = FakeAdapter(verify_error=AuthenticationError("expired code"))
    try:
        asyncio.run(_confirm_code(adapter, "123456"))
        assert False, "expected AuthenticationError"
    except AuthenticationError:
        pass
