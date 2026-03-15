"""Tests for PajGpsEntity base class."""

from __future__ import annotations

from homeassistant.components.paj_gps.coordinator import PajGpsData
from homeassistant.components.paj_gps.entity import PajGpsEntity

from .test_common import make_coordinator, make_device


def _make_entity(device_id: int = 1, in_data: bool = True) -> PajGpsEntity:
    """Instantiate a bare PajGpsEntity for the given device_id."""
    coord = make_coordinator()
    coord.data = PajGpsData(
        devices={device_id: make_device(device_id)} if in_data else {},
        positions={},
    )
    return PajGpsEntity(coord, device_id)


def test_device_info_populated_at_init() -> None:
    """DeviceInfo must be set immediately after __init__, before any property access."""
    entity = _make_entity(1)
    assert entity._attr_device_info is not None


def test_device_info_contains_correct_identifiers() -> None:
    """Identifiers must use user_id and device_id."""
    entity = _make_entity(1)
    assert ("paj_gps", "42_1") in entity._attr_device_info["identifiers"]


def test_device_info_contains_name() -> None:
    """DeviceInfo name must match the device name from coordinator data."""
    entity = _make_entity(1)
    assert entity._attr_device_info["name"] == "Device 1"


def test_device_info_manufacturer_is_paj_gps() -> None:
    """Manufacturer must always be 'PAJ GPS'."""
    entity = _make_entity(1)
    assert entity._attr_device_info["manufacturer"] == "PAJ GPS"


def test_device_info_is_none_when_device_absent() -> None:
    """DeviceInfo must be None when the device is not in coordinator.data at construction time."""
    entity = _make_entity(1, in_data=False)
    assert entity._attr_device_info is None


def test_device_info_cached_object_is_stable() -> None:
    """The same DeviceInfo object must be returned on repeated access (no re-build)."""
    entity = _make_entity(1)
    first_device_info = entity._attr_device_info
    second_device_info = entity._attr_device_info
    assert first_device_info is second_device_info
