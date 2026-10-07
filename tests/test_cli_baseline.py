import asyncio

import pytest

from tripwire import baseline, reporting
from tripwire.cli import _capture_baseline, _run_check
from tripwire.eero_adapter import AuthenticationError

NETWORKS_RESPONSE = {"meta": {"code": 200}, "data": {"networks": [{"id": 1001, "name": "Home", "status": "connected"}]}}
EEROS_RESPONSE = {"meta": {"code": 200}, "data": []}
PROFILES_RESPONSE = {"meta": {"code": 200}, "data": []}
DEVICES_RESPONSE = {"meta": {"code": 200}, "data": []}

ONE_DEVICE_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {
            "mac": "11:11:11:11:11:11",
            "nickname": None,
            "hostname": "new-device",
            "display_name": "new-device",
            "connected": True,
            "wireless": True,
            "connection_type": "wireless",
            "source": {},
            "manufacturer": "Acme",
            "ip": "192.168.1.20",
            "is_guest": False,
            "paused": False,
        }
    ],
}


class FakeAdapter:
    def __init__(self, *, authenticated: bool, devices=DEVICES_RESPONSE):
        self.is_authenticated = authenticated
        self.entered = False
        self.devices = devices

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc_info):
        pass

    async def get_networks(self):
        return NETWORKS_RESPONSE

    async def get_eeros(self, network_id):
        return EEROS_RESPONSE

    async def get_profiles(self, network_id):
        return PROFILES_RESPONSE

    async def get_devices(self, network_id):
        return self.devices


def test_capture_baseline_rejects_unauthenticated_adapter(tmp_path):
    adapter = FakeAdapter(authenticated=False)
    path = tmp_path / "baseline.json"

    with pytest.raises(AuthenticationError):
        asyncio.run(_capture_baseline(adapter, path))

    assert adapter.entered is True
    assert not path.exists()


def test_capture_baseline_writes_a_baseline_when_authenticated(tmp_path):
    adapter = FakeAdapter(authenticated=True)
    path = tmp_path / "baseline.json"

    snapshot = asyncio.run(_capture_baseline(adapter, path))

    assert snapshot.network.id == "1001"
    assert baseline.load(path) == snapshot


def test_run_check_rejects_unauthenticated_adapter(tmp_path):
    path = tmp_path / "baseline.json"
    asyncio.run(_capture_baseline(FakeAdapter(authenticated=True), path))

    with pytest.raises(AuthenticationError):
        asyncio.run(_run_check(FakeAdapter(authenticated=False), path))


def test_run_check_reports_no_changes_against_its_own_baseline(tmp_path):
    path = tmp_path / "baseline.json"
    asyncio.run(_capture_baseline(FakeAdapter(authenticated=True), path))

    comparison = asyncio.run(_run_check(FakeAdapter(authenticated=True), path))

    assert comparison.added == []
    assert comparison.removed == []
    assert reporting.has_changes(comparison) is False


def test_run_check_feeds_a_detected_change_into_has_changes(tmp_path):
    path = tmp_path / "baseline.json"
    asyncio.run(_capture_baseline(FakeAdapter(authenticated=True), path))

    comparison = asyncio.run(
        _run_check(FakeAdapter(authenticated=True, devices=ONE_DEVICE_RESPONSE), path)
    )

    assert len(comparison.added) == 1
    assert reporting.has_changes(comparison) is True
