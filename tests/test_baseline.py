import asyncio
import json

import pytest

from tripwire import baseline
from tripwire.eero_adapter import TransportError
from tripwire.scanner import Device, Network, Node, Profile, Snapshot

SNAPSHOT = Snapshot(
    network=Network(id="1001", name="Home Network", status="connected"),
    nodes=[
        Node(
            id="2001",
            serial="SERIAL001",
            location="Living Room",
            model="eero Pro 6",
            mac_address="AA:BB:CC:00:00:01",
            ip_address="192.168.1.1",
            is_primary=True,
            is_gateway=True,
            status="green",
        ),
    ],
    profiles=[
        Profile(id="9001", name="Media", is_default=False, settings={"paused": False}),
    ],
    devices=[
        Device(
            mac="11:22:33:44:55:66",
            nickname="Mike's Phone",
            hostname="mikes-iphone",
            display_name="Mike's Phone",
            connected=True,
            wireless=True,
            connection_type="wireless",
            node_id="2001",
            node_location="Living Room",
            manufacturer="Apple, Inc.",
            ip="192.168.1.50",
            is_guest=False,
            paused=False,
            group="Media",
        ),
    ],
)


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "baseline.json"
    baseline.save(SNAPSHOT, path)
    loaded = baseline.load(path)
    assert loaded == SNAPSHOT


def test_save_writes_a_schema_version(tmp_path):
    path = tmp_path / "baseline.json"
    baseline.save(SNAPSHOT, path)
    record = json.loads(path.read_text())
    assert record["schema_version"] == baseline.SCHEMA_VERSION


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "baseline.json"
    baseline.save(SNAPSHOT, path)
    assert path.exists()


def test_load_missing_file_raises_baseline_error(tmp_path):
    with pytest.raises(baseline.BaselineError):
        baseline.load(tmp_path / "does-not-exist.json")


def test_load_rejects_wrong_schema_version(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"schema_version": 999, "network": {}, "nodes": [], "profiles": [], "devices": []}))
    with pytest.raises(baseline.BaselineError):
        baseline.load(path)


def test_load_rejects_malformed_record(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"schema_version": baseline.SCHEMA_VERSION, "network": {"id": "1"}}))
    with pytest.raises(baseline.BaselineError):
        baseline.load(path)


def test_load_rejects_invalid_json(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text("not json")
    with pytest.raises(baseline.BaselineError):
        baseline.load(path)


def test_save_leaves_no_temp_file_behind(tmp_path):
    path = tmp_path / "baseline.json"
    baseline.save(SNAPSHOT, path)
    assert list(tmp_path.iterdir()) == [path]


class FakeScanner:
    def __init__(self, *, result: Snapshot | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.scan_calls = 0

    async def scan(self) -> Snapshot:
        self.scan_calls += 1
        if self.error:
            raise self.error
        return self.result


def test_capture_saves_the_scanned_snapshot(tmp_path):
    path = tmp_path / "baseline.json"
    scanner = FakeScanner(result=SNAPSHOT)

    returned = asyncio.run(baseline.capture(scanner, path))

    assert returned == SNAPSHOT
    assert baseline.load(path) == SNAPSHOT


def test_capture_does_not_create_a_file_when_scan_fails(tmp_path):
    path = tmp_path / "baseline.json"
    scanner = FakeScanner(error=TransportError("offline"))

    with pytest.raises(TransportError):
        asyncio.run(baseline.capture(scanner, path))

    assert not path.exists()


def test_capture_leaves_an_existing_baseline_untouched_when_scan_fails(tmp_path):
    path = tmp_path / "baseline.json"
    baseline.save(SNAPSHOT, path)
    before = path.read_text()
    scanner = FakeScanner(error=TransportError("offline"))

    with pytest.raises(TransportError):
        asyncio.run(baseline.capture(scanner, path))

    assert path.read_text() == before


def test_evaluate_compares_scan_against_the_saved_baseline(tmp_path):
    path = tmp_path / "baseline.json"
    baseline.save(SNAPSHOT, path)
    scanner = FakeScanner(result=SNAPSHOT)

    result = asyncio.run(baseline.evaluate(scanner, path))

    assert result.added == []
    assert result.removed == []
    assert result.renamed == []
    assert result.changed == []
    assert result.regrouped == []


def test_evaluate_propagates_scan_failure_without_touching_the_baseline(tmp_path):
    path = tmp_path / "baseline.json"
    baseline.save(SNAPSHOT, path)
    before = path.read_text()
    scanner = FakeScanner(error=TransportError("offline"))

    with pytest.raises(TransportError):
        asyncio.run(baseline.evaluate(scanner, path))

    assert path.read_text() == before


def test_evaluate_raises_baseline_error_when_no_baseline_exists(tmp_path):
    scanner = FakeScanner(result=SNAPSHOT)
    with pytest.raises(baseline.BaselineError):
        asyncio.run(baseline.evaluate(scanner, tmp_path / "missing.json"))
