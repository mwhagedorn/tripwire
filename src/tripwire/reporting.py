"""Reporting: render a `Comparison` as concise text or JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .scanner import Comparison, Device, DeviceChange


def has_changes(comparison: Comparison) -> bool:
    return bool(
        comparison.added
        or comparison.removed
        or comparison.renamed
        or comparison.changed
        or comparison.regrouped
    )


def _device_label(device: Device) -> str:
    name = device.nickname or device.hostname or device.display_name or device.mac
    return f"{name} ({device.mac}) [{device.group}]"


def _device_name(device: Device) -> str:
    return device.nickname or device.hostname or device.display_name or device.mac


def render_text(comparison: Comparison) -> str:
    if not has_changes(comparison):
        return "No changes."

    sections: list[str] = []

    if comparison.added:
        lines = [f"  + {_device_label(device)}" for device in comparison.added]
        sections.append("Added:\n" + "\n".join(lines))

    if comparison.removed:
        lines = [f"  - {_device_label(device)}" for device in comparison.removed]
        sections.append("Removed:\n" + "\n".join(lines))

    if comparison.renamed:
        lines = [
            f"  * {_device_name(change.old)} -> {_device_name(change.new)} ({change.new.mac})"
            for change in comparison.renamed
        ]
        sections.append("Renamed:\n" + "\n".join(lines))

    if comparison.changed:
        lines = [f"  * {_device_label(change.new)}" for change in comparison.changed]
        sections.append("Changed:\n" + "\n".join(lines))

    if comparison.regrouped:
        lines = [
            f"  * {_device_name(change.new)} ({change.new.mac}): {change.old.group} -> {change.new.group}"
            for change in comparison.regrouped
        ]
        sections.append("Regrouped:\n" + "\n".join(lines))

    return "\n\n".join(sections)


def _change_dict(change: DeviceChange) -> dict[str, Any]:
    return {"old": asdict(change.old), "new": asdict(change.new)}


def to_dict(comparison: Comparison) -> dict[str, Any]:
    return {
        "added": [asdict(device) for device in comparison.added],
        "removed": [asdict(device) for device in comparison.removed],
        "renamed": [_change_dict(change) for change in comparison.renamed],
        "changed": [_change_dict(change) for change in comparison.changed],
        "regrouped": [_change_dict(change) for change in comparison.regrouped],
    }


def render_json(comparison: Comparison) -> str:
    return json.dumps(to_dict(comparison), indent=2, sort_keys=True)
