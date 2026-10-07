from tripwire.scanner import UNGROUPED, Device, Network, Snapshot, compare

NETWORK = Network(id="1001", name="Home Network", status="connected")


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


def _snapshot(*devices: Device) -> Snapshot:
    return Snapshot(network=NETWORK, nodes=[], profiles=[], devices=list(devices))


def test_compare_detects_added_device():
    old = _device("11:11:11:11:11:11")
    new_device = _device("22:22:22:22:22:22")

    result = compare(_snapshot(old), _snapshot(old, new_device))

    assert result.added == [new_device]
    assert result.removed == []


def test_compare_detects_removed_device():
    staying = _device("11:11:11:11:11:11")
    leaving = _device("22:22:22:22:22:22")

    result = compare(_snapshot(staying, leaving), _snapshot(staying))

    assert result.removed == [leaving]
    assert result.added == []


def test_compare_reports_no_changes_for_identical_snapshots():
    device = _device("11:11:11:11:11:11")

    result = compare(_snapshot(device), _snapshot(device))

    assert result.added == []
    assert result.removed == []


def test_compare_matches_devices_by_mac_not_identity():
    old = _device("11:11:11:11:11:11", nickname="Old Name")
    new = _device("11:11:11:11:11:11", nickname="New Name")

    result = compare(_snapshot(old), _snapshot(new))

    assert result.added == []
    assert result.removed == []


def test_compare_detects_rename():
    old = _device("11:11:11:11:11:11", nickname="Old Name")
    new = _device("11:11:11:11:11:11", nickname="New Name")

    result = compare(_snapshot(old), _snapshot(new))

    assert len(result.renamed) == 1
    assert result.renamed[0].old is old
    assert result.renamed[0].new is new
    assert result.changed == []


def test_compare_detects_change_in_connection_fields():
    old = _device("11:11:11:11:11:11", connected=True, node_location="Living Room")
    new = _device("11:11:11:11:11:11", connected=False, node_location="Bedroom")

    result = compare(_snapshot(old), _snapshot(new))

    assert len(result.changed) == 1
    assert result.changed[0].old is old
    assert result.changed[0].new is new
    assert result.renamed == []


def test_compare_device_can_be_both_renamed_and_changed():
    old = _device("11:11:11:11:11:11", nickname="Old Name", connected=True)
    new = _device("11:11:11:11:11:11", nickname="New Name", connected=False)

    result = compare(_snapshot(old), _snapshot(new))

    assert len(result.renamed) == 1
    assert len(result.changed) == 1


def test_compare_ignores_group_field_for_renamed_and_changed():
    old = _device("11:11:11:11:11:11", group="Media")
    new = _device("11:11:11:11:11:11", group="Gaming")

    result = compare(_snapshot(old), _snapshot(new))

    assert result.renamed == []
    assert result.changed == []


def test_compare_skips_renamed_and_changed_for_added_or_removed_devices():
    added_device = _device("22:22:22:22:22:22")
    result = compare(_snapshot(), _snapshot(added_device))

    assert result.added == [added_device]
    assert result.renamed == []
    assert result.changed == []


def test_compare_detects_regroup_between_named_groups():
    old = _device("11:11:11:11:11:11", group="Media")
    new = _device("11:11:11:11:11:11", group="Gaming")

    result = compare(_snapshot(old), _snapshot(new))

    assert len(result.regrouped) == 1
    assert result.regrouped[0].old is old
    assert result.regrouped[0].new is new


def test_compare_detects_device_moving_into_ungrouped():
    old = _device("11:11:11:11:11:11", group="Media")
    new = _device("11:11:11:11:11:11", group=UNGROUPED)

    result = compare(_snapshot(old), _snapshot(new))

    assert len(result.regrouped) == 1
    assert result.regrouped[0].new.group == UNGROUPED


def test_compare_detects_device_moving_out_of_ungrouped():
    old = _device("11:11:11:11:11:11", group=UNGROUPED)
    new = _device("11:11:11:11:11:11", group="Media")

    result = compare(_snapshot(old), _snapshot(new))

    assert len(result.regrouped) == 1
    assert result.regrouped[0].old.group == UNGROUPED


def test_compare_reports_no_regroup_when_group_is_unchanged():
    old = _device("11:11:11:11:11:11", group="Media")
    new = _device("11:11:11:11:11:11", group="Media")

    result = compare(_snapshot(old), _snapshot(new))

    assert result.regrouped == []
