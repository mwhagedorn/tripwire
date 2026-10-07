import json

from tripwire.reporting import has_changes, render_json, render_text, to_dict
from tripwire.scanner import UNGROUPED, Comparison, Device, DeviceChange


def _device(mac: str, **overrides) -> Device:
    defaults = dict(
        mac=mac,
        nickname=None,
        hostname="device",
        display_name="device",
        connected=True,
        wireless=True,
        connection_type="wireless",
        node_id="2001",
        node_location="Living Room",
        manufacturer="Acme",
        ip="192.168.1.10",
        is_guest=False,
        paused=False,
        group="Media",
    )
    defaults.update(overrides)
    return Device(**defaults)


EMPTY = Comparison(added=[], removed=[], renamed=[], changed=[], regrouped=[])


def test_render_text_reports_no_changes():
    assert render_text(EMPTY) == "No changes."


def test_has_changes_false_for_empty_comparison():
    assert has_changes(EMPTY) is False


def test_has_changes_true_when_any_category_is_non_empty():
    device = _device("11:11:11:11:11:11")
    assert has_changes(Comparison(added=[device], removed=[], renamed=[], changed=[], regrouped=[])) is True
    assert has_changes(Comparison(added=[], removed=[device], renamed=[], changed=[], regrouped=[])) is True


def test_render_text_shows_added_devices_with_group():
    device = _device("11:11:11:11:11:11", nickname="Mike's Phone", group="Media")
    comparison = Comparison(added=[device], removed=[], renamed=[], changed=[], regrouped=[])

    text = render_text(comparison)

    assert "Added:" in text
    assert "Mike's Phone" in text
    assert "11:11:11:11:11:11" in text
    assert "[Media]" in text


def test_render_text_shows_ungrouped_explicitly():
    device = _device("11:11:11:11:11:11", group=UNGROUPED)
    comparison = Comparison(added=[device], removed=[], renamed=[], changed=[], regrouped=[])

    assert "[Ungrouped]" in render_text(comparison)


def test_render_text_shows_removed_devices():
    device = _device("22:22:22:22:22:22", nickname="Old Device")
    comparison = Comparison(added=[], removed=[device], renamed=[], changed=[], regrouped=[])

    text = render_text(comparison)

    assert "Removed:" in text
    assert "Old Device" in text


def test_render_text_shows_renamed_devices():
    old = _device("11:11:11:11:11:11", nickname="Old Name")
    new = _device("11:11:11:11:11:11", nickname="New Name")
    comparison = Comparison(
        added=[], removed=[], renamed=[DeviceChange(old=old, new=new)], changed=[], regrouped=[]
    )

    text = render_text(comparison)

    assert "Renamed:" in text
    assert "Old Name -> New Name" in text


def test_render_text_shows_changed_devices():
    old = _device("11:11:11:11:11:11", connected=True)
    new = _device("11:11:11:11:11:11", connected=False)
    comparison = Comparison(
        added=[], removed=[], renamed=[], changed=[DeviceChange(old=old, new=new)], regrouped=[]
    )

    assert "Changed:" in render_text(comparison)


def test_render_text_shows_regrouped_devices():
    old = _device("11:11:11:11:11:11", group="Media")
    new = _device("11:11:11:11:11:11", group=UNGROUPED)
    comparison = Comparison(
        added=[], removed=[], renamed=[], changed=[], regrouped=[DeviceChange(old=old, new=new)]
    )

    text = render_text(comparison)

    assert "Regrouped:" in text
    assert "Media -> Ungrouped" in text


def test_render_text_includes_every_section_when_all_present():
    device = _device("33:33:33:33:33:33")
    old = _device("11:11:11:11:11:11")
    new = _device("11:11:11:11:11:11", nickname="New Name")
    comparison = Comparison(
        added=[device],
        removed=[device],
        renamed=[DeviceChange(old=old, new=new)],
        changed=[DeviceChange(old=old, new=new)],
        regrouped=[DeviceChange(old=old, new=new)],
    )

    text = render_text(comparison)

    for heading in ("Added:", "Removed:", "Renamed:", "Changed:", "Regrouped:"):
        assert heading in text


def test_render_json_is_valid_and_round_trips():
    device = _device("11:11:11:11:11:11", nickname="Mike's Phone")
    old = _device("22:22:22:22:22:22")
    new = _device("22:22:22:22:22:22", nickname="New Name")
    comparison = Comparison(
        added=[device],
        removed=[],
        renamed=[DeviceChange(old=old, new=new)],
        changed=[],
        regrouped=[],
    )

    text = render_json(comparison)
    parsed = json.loads(text)

    assert parsed["added"][0]["mac"] == "11:11:11:11:11:11"
    assert parsed["added"][0]["nickname"] == "Mike's Phone"
    assert parsed["renamed"][0]["old"]["mac"] == "22:22:22:22:22:22"
    assert parsed["renamed"][0]["new"]["nickname"] == "New Name"
    assert parsed["removed"] == []
    assert parsed["changed"] == []
    assert parsed["regrouped"] == []


def test_to_dict_covers_every_change_category():
    device = _device("11:11:11:11:11:11")
    old = _device("22:22:22:22:22:22")
    new = _device("22:22:22:22:22:22", nickname="New Name")
    comparison = Comparison(
        added=[device],
        removed=[device],
        renamed=[DeviceChange(old=old, new=new)],
        changed=[DeviceChange(old=old, new=new)],
        regrouped=[DeviceChange(old=old, new=new)],
    )

    result = to_dict(comparison)

    assert set(result.keys()) == {"added", "removed", "renamed", "changed", "regrouped"}
    for key in result:
        assert len(result[key]) == 1


def test_render_json_of_empty_comparison_has_empty_lists():
    parsed = json.loads(render_json(EMPTY))
    assert parsed == {"added": [], "removed": [], "renamed": [], "changed": [], "regrouped": []}
