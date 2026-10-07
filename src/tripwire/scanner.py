"""Scanner: fetch the current Eero network state and normalize it into a snapshot.

Field names here come from observing real (redacted) responses against a
live account, not from any published schema -- this is an undocumented
API. Keys this module doesn't recognize are ignored rather than rejected,
since response drift is an accepted risk (see README.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .eero_adapter import EeroAdapter

UNGROUPED = "Ungrouped"


def _id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1]


def _extract_list(envelope: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    data = envelope.get("data", {})
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


@dataclass(frozen=True)
class Network:
    id: str
    name: str
    status: str | None


@dataclass(frozen=True)
class Node:
    id: str
    serial: str | None
    location: str | None
    model: str | None
    mac_address: str | None
    ip_address: str | None
    is_primary: bool
    is_gateway: bool
    status: str | None


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    is_default: bool
    settings: dict[str, Any]


@dataclass(frozen=True)
class Device:
    mac: str
    nickname: str | None
    hostname: str | None
    display_name: str | None
    connected: bool
    wireless: bool
    connection_type: str | None
    node_id: str | None
    node_location: str | None
    manufacturer: str | None
    ip: str | None
    is_guest: bool
    paused: bool
    group: str


@dataclass(frozen=True)
class Snapshot:
    network: Network
    nodes: list[Node]
    profiles: list[Profile]
    devices: list[Device]


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "network": asdict(snapshot.network),
        "nodes": [asdict(node) for node in snapshot.nodes],
        "profiles": [asdict(profile) for profile in snapshot.profiles],
        "devices": [asdict(device) for device in snapshot.devices],
    }


def _normalize_network(raw: dict[str, Any]) -> Network:
    return Network(
        id=str(raw.get("id") or _id_from_url(raw.get("url"))),
        name=raw.get("name", ""),
        status=raw.get("status"),
    )


def _normalize_node(raw: dict[str, Any]) -> Node:
    return Node(
        id=_id_from_url(raw.get("url")) or "",
        serial=raw.get("serial"),
        location=raw.get("location"),
        model=raw.get("model"),
        mac_address=raw.get("mac_address"),
        ip_address=raw.get("ip_address"),
        is_primary=bool(raw.get("is_primary_node")),
        is_gateway=bool(raw.get("gateway")),
        status=raw.get("status"),
    )


_PROFILE_SETTINGS_EXCLUDED_KEYS = ("devices", "proxied_nodes")


def _normalize_profile(raw: dict[str, Any]) -> Profile:
    return Profile(
        id=_id_from_url(raw.get("url")) or "",
        name=raw.get("name", ""),
        is_default=bool(raw.get("default")),
        settings={k: v for k, v in raw.items() if k not in _PROFILE_SETTINGS_EXCLUDED_KEYS},
    )


def _device_group(raw_profile: dict[str, Any] | None, default_profile_id: str | None) -> str:
    """Resolve a device's group name.

    Eero represents "no group" as membership in its own catch-all profile
    (flagged `default: true` in the profiles list), not as a null/missing
    `profile` field on the device -- every device carries one. A profile
    matching `default_profile_id`, or no profile at all, normalizes to
    `UNGROUPED`.
    """
    if not raw_profile:
        return UNGROUPED
    name = raw_profile.get("name")
    if not name:
        return UNGROUPED
    if default_profile_id is not None and _id_from_url(raw_profile.get("url")) == default_profile_id:
        return UNGROUPED
    return name


def _normalize_device(raw: dict[str, Any], default_profile_id: str | None) -> Device:
    source = raw.get("source") or {}
    return Device(
        mac=raw.get("mac", ""),
        nickname=raw.get("nickname"),
        hostname=raw.get("hostname"),
        display_name=raw.get("display_name"),
        connected=bool(raw.get("connected")),
        wireless=bool(raw.get("wireless")),
        connection_type=raw.get("connection_type"),
        node_id=_id_from_url(source.get("url")),
        node_location=source.get("location"),
        manufacturer=raw.get("manufacturer"),
        ip=raw.get("ip"),
        is_guest=bool(raw.get("is_guest")),
        paused=bool(raw.get("paused")),
        group=_device_group(raw.get("profile"), default_profile_id),
    )


class Scanner:
    """Fetches the current network snapshot through an `EeroAdapter`."""

    def __init__(self, adapter: EeroAdapter) -> None:
        self._adapter = adapter

    async def scan(self) -> Snapshot:
        networks_response = await self._adapter.get_networks()
        networks = _extract_list(networks_response, "networks")
        if not networks:
            raise ValueError("No networks returned for this account")
        network = _normalize_network(networks[0])

        eeros_response = await self._adapter.get_eeros(network.id)
        nodes = [_normalize_node(raw) for raw in _extract_list(eeros_response)]

        profiles_response = await self._adapter.get_profiles(network.id)
        profiles = [_normalize_profile(raw) for raw in _extract_list(profiles_response)]
        default_profile_id = next((profile.id for profile in profiles if profile.is_default), None)

        devices_response = await self._adapter.get_devices(network.id)
        devices = [
            _normalize_device(raw, default_profile_id) for raw in _extract_list(devices_response)
        ]

        return Snapshot(network=network, nodes=nodes, profiles=profiles, devices=devices)


@dataclass(frozen=True)
class DeviceChange:
    old: Device
    new: Device


@dataclass(frozen=True)
class Comparison:
    added: list[Device]
    removed: list[Device]
    renamed: list[DeviceChange]
    changed: list[DeviceChange]
    regrouped: list[DeviceChange]


_NAME_FIELDS = ("nickname", "hostname", "display_name")
_CHANGE_FIELDS = (
    "connected",
    "wireless",
    "connection_type",
    "node_id",
    "node_location",
    "manufacturer",
    "ip",
    "is_guest",
    "paused",
)


def _differs(old: Device, new: Device, fields: tuple[str, ...]) -> bool:
    return any(getattr(old, field) != getattr(new, field) for field in fields)


def compare(baseline: Snapshot, current: Snapshot) -> Comparison:
    """Compare two snapshots by matching devices on their MAC address.

    A device matched in both snapshots can appear in both `renamed` and
    `changed` if both kinds of fields differ -- the two categories are
    independent, not mutually exclusive. `regrouped` covers a `group`
    change, including a transition into or out of `UNGROUPED`, which is
    just an ordinary value of that field, not a special case.
    """
    baseline_by_mac = {device.mac: device for device in baseline.devices}
    current_by_mac = {device.mac: device for device in current.devices}

    added = [device for mac, device in current_by_mac.items() if mac not in baseline_by_mac]
    removed = [device for mac, device in baseline_by_mac.items() if mac not in current_by_mac]

    renamed = []
    changed = []
    regrouped = []
    for mac, new_device in current_by_mac.items():
        old_device = baseline_by_mac.get(mac)
        if old_device is None:
            continue
        if _differs(old_device, new_device, _NAME_FIELDS):
            renamed.append(DeviceChange(old=old_device, new=new_device))
        if _differs(old_device, new_device, _CHANGE_FIELDS):
            changed.append(DeviceChange(old=old_device, new=new_device))
        if old_device.group != new_device.group:
            regrouped.append(DeviceChange(old=old_device, new=new_device))

    return Comparison(
        added=added, removed=removed, renamed=renamed, changed=changed, regrouped=regrouped
    )
