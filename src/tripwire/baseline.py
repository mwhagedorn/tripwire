"""Baseline storage: serialize and load a saved network `Snapshot`."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .scanner import (
    Comparison,
    Device,
    Network,
    Node,
    Profile,
    Scanner,
    Snapshot,
    compare,
    snapshot_to_dict,
)

SCHEMA_VERSION = 1


class BaselineError(Exception):
    """Raised when a baseline file can't be saved or loaded."""


def save(snapshot: Snapshot, path: Path | str) -> None:
    """Write `snapshot` to `path` atomically, so a crash mid-write can never
    leave a partial or corrupted baseline file on disk."""
    path = Path(path)
    record = {"schema_version": SCHEMA_VERSION, **snapshot_to_dict(snapshot)}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(record, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def load(path: Path | str) -> Snapshot:
    """Load a `Snapshot` previously written by `save`.

    Raises:
        BaselineError: if the file is missing, not valid JSON, carries a
            schema_version other than the one this module writes, or is
            otherwise malformed.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"Could not read baseline at {path}: {exc}") from exc

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise BaselineError(
            f"Unsupported baseline schema_version {version!r} at {path} (expected {SCHEMA_VERSION})"
        )

    try:
        return Snapshot(
            network=Network(**raw["network"]),
            nodes=[Node(**node) for node in raw["nodes"]],
            profiles=[Profile(**profile) for profile in raw["profiles"]],
            devices=[Device(**device) for device in raw["devices"]],
        )
    except (KeyError, TypeError) as exc:
        raise BaselineError(f"Malformed baseline at {path}: {exc}") from exc


async def capture(scanner: Scanner, path: Path | str) -> Snapshot:
    """Scan and atomically save a fresh baseline to `path`.

    If `scanner.scan()` itself raises (an `AdapterError` subclass, or
    `ValueError` when the account has no networks), nothing is written --
    a baseline already at `path` is left completely untouched. `save` is
    only ever reached after a fully successful scan.
    """
    snapshot = await scanner.scan()
    save(snapshot, path)
    return snapshot


async def evaluate(scanner: Scanner, path: Path | str) -> Comparison:
    """Scan and compare the result against the baseline at `path`.

    Raises whatever `scanner.scan()` raises on a failed scan -- a caller
    can distinguish that from a successful `Comparison` with every list
    empty ("no changes found"). Never writes to `path`.
    """
    previous = load(path)
    current = await scanner.scan()
    return compare(previous, current)
