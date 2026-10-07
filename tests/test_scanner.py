import asyncio

from tripwire.scanner import UNGROUPED, Scanner, snapshot_to_dict

NETWORKS_RESPONSE = {
    "meta": {"code": 200},
    "data": {
        "networks": [
            {"id": 1001, "name": "Home Network", "status": "connected"},
        ]
    },
}

EEROS_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {
            "url": "/2.2/eeros/2001",
            "serial": "SERIAL001",
            "location": "Living Room",
            "model": "eero Pro 6",
            "mac_address": "AA:BB:CC:00:00:01",
            "ip_address": "192.168.1.1",
            "is_primary_node": True,
            "gateway": True,
            "status": "green",
        },
        {
            "url": "/2.2/eeros/2002",
            "serial": "SERIAL002",
            "location": "Bedroom",
            "model": "eero Pro 6",
            "mac_address": "AA:BB:CC:00:00:02",
            "ip_address": "192.168.1.2",
            "is_primary_node": False,
            "gateway": False,
            "status": "green",
        },
    ],
}

PROFILES_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {"url": "/2.2/networks/1001/profiles/9001", "name": "Media", "default": False},
        {"url": "/2.2/networks/1001/profiles/9002", "name": "Unassigned", "default": True},
    ],
}

DEVICES_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {
            "mac": "11:22:33:44:55:66",
            "nickname": "Mike's Phone",
            "hostname": "mikes-iphone",
            "display_name": "Mike's Phone",
            "connected": True,
            "wireless": True,
            "connection_type": "wireless",
            "source": {"url": "/2.2/eeros/2001", "location": "Living Room"},
            "manufacturer": "Apple, Inc.",
            "ip": "192.168.1.50",
            "is_guest": False,
            "paused": False,
            "profile": {"url": "/2.2/networks/1001/profiles/9001", "name": "Media", "paused": False},
        },
        {
            "mac": "77:88:99:aa:bb:cc",
            "nickname": None,
            "hostname": "unknown-device",
            "display_name": "unknown-device",
            "connected": False,
            "wireless": True,
            "connection_type": "wireless",
            "source": {"url": "/2.2/eeros/2002", "location": "Bedroom"},
            "manufacturer": "Unknown",
            "ip": None,
            "is_guest": False,
            "paused": False,
            "profile": {
                "url": "/2.2/networks/1001/profiles/9002",
                "name": "Unassigned",
                "paused": False,
            },
        },
    ],
}


class FakeAdapter:
    def __init__(self):
        self.calls: list[tuple[str, str | None]] = []

    async def get_networks(self):
        self.calls.append(("get_networks", None))
        return NETWORKS_RESPONSE

    async def get_eeros(self, network_id: str):
        self.calls.append(("get_eeros", network_id))
        return EEROS_RESPONSE

    async def get_profiles(self, network_id: str):
        self.calls.append(("get_profiles", network_id))
        return PROFILES_RESPONSE

    async def get_devices(self, network_id: str):
        self.calls.append(("get_devices", network_id))
        return DEVICES_RESPONSE


def test_scan_normalizes_network_nodes_and_devices():
    scanner = Scanner(FakeAdapter())
    snapshot = asyncio.run(scanner.scan())

    assert snapshot.network.id == "1001"
    assert snapshot.network.name == "Home Network"
    assert snapshot.network.status == "connected"

    assert [node.id for node in snapshot.nodes] == ["2001", "2002"]
    assert snapshot.nodes[0].location == "Living Room"
    assert snapshot.nodes[0].is_primary is True
    assert snapshot.nodes[0].is_gateway is True
    assert snapshot.nodes[1].is_primary is False

    assert [device.mac for device in snapshot.devices] == [
        "11:22:33:44:55:66",
        "77:88:99:aa:bb:cc",
    ]
    assert snapshot.devices[0].nickname == "Mike's Phone"
    assert snapshot.devices[0].node_id == "2001"
    assert snapshot.devices[0].node_location == "Living Room"
    assert snapshot.devices[0].group == "Media"
    assert snapshot.devices[1].nickname is None
    assert snapshot.devices[1].connected is False
    assert snapshot.devices[1].group == UNGROUPED

    assert [profile.name for profile in snapshot.profiles] == ["Media", "Unassigned"]
    assert snapshot.profiles[1].is_default is True


def test_scan_uses_the_discovered_network_id_for_followup_calls():
    adapter = FakeAdapter()
    asyncio.run(Scanner(adapter).scan())

    assert adapter.calls == [
        ("get_networks", None),
        ("get_eeros", "1001"),
        ("get_profiles", "1001"),
        ("get_devices", "1001"),
    ]


def test_device_with_no_profile_field_is_ungrouped():
    class NoProfileAdapter(FakeAdapter):
        async def get_devices(self, network_id: str):
            response = {"meta": {"code": 200}, "data": [dict(DEVICES_RESPONSE["data"][0])]}
            del response["data"][0]["profile"]
            return response

    snapshot = asyncio.run(Scanner(NoProfileAdapter()).scan())
    assert snapshot.devices[0].group == UNGROUPED


def test_scan_raises_when_no_networks_are_returned():
    class EmptyAdapter(FakeAdapter):
        async def get_networks(self):
            return {"meta": {"code": 200}, "data": {"networks": []}}

    try:
        asyncio.run(Scanner(EmptyAdapter()).scan())
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_scan_tolerates_unknown_fields():
    class ExtraFieldAdapter(FakeAdapter):
        async def get_networks(self):
            response = NETWORKS_RESPONSE.copy()
            response["data"] = dict(response["data"])
            response["data"]["networks"] = [
                {**NETWORKS_RESPONSE["data"]["networks"][0], "some_new_field": {"nested": True}}
            ]
            return response

    snapshot = asyncio.run(Scanner(ExtraFieldAdapter()).scan())
    assert snapshot.network.name == "Home Network"


def test_normalize_node_with_only_a_url_has_none_for_every_other_field():
    class SparseEerosAdapter(FakeAdapter):
        async def get_eeros(self, network_id: str):
            return {"meta": {"code": 200}, "data": [{"url": "/2.2/eeros/3001"}]}

    snapshot = asyncio.run(Scanner(SparseEerosAdapter()).scan())

    assert len(snapshot.nodes) == 1
    node = snapshot.nodes[0]
    assert node.id == "3001"
    assert node.serial is None
    assert node.location is None
    assert node.model is None
    assert node.mac_address is None
    assert node.ip_address is None
    assert node.status is None
    assert node.is_primary is False
    assert node.is_gateway is False


def test_normalize_device_with_only_a_mac_has_none_for_every_other_field():
    class SparseDevicesAdapter(FakeAdapter):
        async def get_devices(self, network_id: str):
            return {"meta": {"code": 200}, "data": [{"mac": "aa:aa:aa:aa:aa:aa"}]}

    snapshot = asyncio.run(Scanner(SparseDevicesAdapter()).scan())

    assert len(snapshot.devices) == 1
    device = snapshot.devices[0]
    assert device.mac == "aa:aa:aa:aa:aa:aa"
    assert device.nickname is None
    assert device.hostname is None
    assert device.display_name is None
    assert device.manufacturer is None
    assert device.ip is None
    assert device.node_id is None
    assert device.node_location is None
    assert device.connected is False
    assert device.wireless is False
    assert device.is_guest is False
    assert device.paused is False
    assert device.group == UNGROUPED


def test_scan_tolerates_empty_eeros_profiles_and_devices_lists():
    class EmptyListsAdapter(FakeAdapter):
        async def get_eeros(self, network_id: str):
            return {"meta": {"code": 200}, "data": []}

        async def get_profiles(self, network_id: str):
            return {"meta": {"code": 200}, "data": []}

        async def get_devices(self, network_id: str):
            return {"meta": {"code": 200}, "data": []}

    snapshot = asyncio.run(Scanner(EmptyListsAdapter()).scan())

    assert snapshot.nodes == []
    assert snapshot.profiles == []
    assert snapshot.devices == []


def test_scan_tolerates_a_response_with_no_data_key_at_all():
    class NoDataKeyAdapter(FakeAdapter):
        async def get_eeros(self, network_id: str):
            return {"meta": {"code": 200}}

        async def get_profiles(self, network_id: str):
            return {"meta": {"code": 200}}

        async def get_devices(self, network_id: str):
            return {"meta": {"code": 200}}

    snapshot = asyncio.run(Scanner(NoDataKeyAdapter()).scan())

    assert snapshot.nodes == []
    assert snapshot.profiles == []
    assert snapshot.devices == []


def test_device_group_is_the_real_profile_name_when_no_profile_is_flagged_default():
    class NoDefaultProfileAdapter(FakeAdapter):
        async def get_profiles(self, network_id: str):
            return {
                "meta": {"code": 200},
                "data": [{"url": "/2.2/networks/1001/profiles/9001", "name": "Media", "default": False}],
            }

    snapshot = asyncio.run(Scanner(NoDefaultProfileAdapter()).scan())

    assert snapshot.devices[0].group == "Media"
    assert snapshot.devices[1].group == "Unassigned"


def test_snapshot_to_dict_has_every_top_level_section():
    snapshot = asyncio.run(Scanner(FakeAdapter()).scan())

    result = snapshot_to_dict(snapshot)

    assert set(result.keys()) == {"network", "nodes", "profiles", "devices"}
    assert result["network"]["id"] == "1001"
    assert result["devices"][0]["mac"] == "11:22:33:44:55:66"
    assert result["devices"][0]["group"] == "Media"


def test_profile_settings_keep_everything_except_devices_and_proxied_nodes():
    class RichProfileAdapter(FakeAdapter):
        async def get_profiles(self, network_id: str):
            return {
                "meta": {"code": 200},
                "data": [
                    {
                        "url": "/2.2/networks/1001/profiles/9001",
                        "name": "Teens",
                        "default": False,
                        "paused": False,
                        "schedule": [],
                        "state": {"value": "on", "schedule": None},
                        "premium_dns": {
                            "dns_policies": {
                                "block_pornographic_content": True,
                                "block_violent_content": True,
                                "safe_search_enabled": True,
                            }
                        },
                        "unified_content_filters": {
                            "dns_policies": {
                                "block_social_content": False,
                                "youtube_restricted": True,
                            }
                        },
                        "devices": [{"mac": "aa:aa:aa:aa:aa:aa"}],
                        "proxied_nodes": [{"mac_address": "bb:bb:bb:bb:bb:bb"}],
                    }
                ],
            }

    snapshot = asyncio.run(Scanner(RichProfileAdapter()).scan())
    profile = snapshot.profiles[0]

    assert "devices" not in profile.settings
    assert "proxied_nodes" not in profile.settings
    assert profile.settings["paused"] is False
    assert profile.settings["schedule"] == []
    assert profile.settings["state"] == {"value": "on", "schedule": None}
    assert profile.settings["premium_dns"]["dns_policies"]["block_pornographic_content"] is True
    assert profile.settings["unified_content_filters"]["dns_policies"]["youtube_restricted"] is True
