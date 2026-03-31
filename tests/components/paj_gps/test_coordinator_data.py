"""Tests for the PajGpsData dataclass."""

from __future__ import annotations

import dataclasses

from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint

from homeassistant.components.paj_gps.coordinator import PajGpsData


def test_default_snapshot_is_empty() -> None:
    """A default PajGpsData instance has empty devices and positions."""
    data = PajGpsData(devices={}, positions={})
    assert data.devices == {}
    assert data.positions == {}


def test_replace_preserves_other_fields() -> None:
    """Replacing one field preserves the other fields unchanged."""
    device = Device(id=1)
    data = PajGpsData(devices={1: device}, positions={})
    tp = TrackPoint(iddevice=1)
    new_data = dataclasses.replace(data, positions={1: tp})

    assert new_data.devices == {1: device}
    assert new_data.positions == {1: tp}
    # Original is untouched (frozen dataclass)
    assert data.positions == {}


def test_snapshot_is_immutable_via_replace() -> None:
    """dataclasses.replace() creates a new object; the original is unchanged."""
    device = Device(id=1)
    original = PajGpsData(devices={1: device}, positions={})
    updated = dataclasses.replace(original, positions={1: TrackPoint(iddevice=1)})

    # replace() returns a distinct object
    assert original is not updated
    # original is untouched
    assert original.positions == {}
    # updated carries the new value
    assert 1 in updated.positions
