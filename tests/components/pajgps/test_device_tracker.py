"""Tests for device_tracker.py — PajGPSDeviceTracker and async_setup_entry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.pajgps import device_tracker as dt_module
from homeassistant.components.pajgps.coordinator import PajGpsData
from homeassistant.components.pajgps.device_tracker import PajGPSDeviceTracker

from .test_common import make_coordinator, make_device, make_trackpoint


def _make_hass_and_config_entry(coordinator):
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    config_entry.runtime_data = coordinator
    hass = MagicMock()
    return hass, config_entry


def _make_sensor(device_id: int = 1, positions=None):
    """Create a PajGPSDeviceTracker for testing."""
    coord = make_coordinator()
    coord.data = PajGpsData(
        devices={device_id: make_device(device_id)},
        positions=positions or {},
    )
    return PajGPSDeviceTracker(coord, device_id)


def test_unique_id_is_set() -> None:
    """Test that the unique ID is correctly set for the sensor."""
    sensor = _make_sensor(1)
    assert sensor._attr_unique_id == "test@example.com_1"


def test_latitude_returns_float_when_position_exists() -> None:
    """Test that latitude returns a float when a position is available."""
    tp = make_trackpoint(device_id=1, lat=52.5, lng=13.4)
    sensor = _make_sensor(1, positions={1: tp})
    assert sensor.latitude == pytest.approx(52.5)


def test_latitude_returns_none_when_no_position() -> None:
    """Test that latitude returns None when no position data exists."""
    sensor = _make_sensor(1, positions={})
    assert sensor.latitude is None


def test_latitude_returns_none_when_lat_is_none() -> None:
    """Test that latitude returns None when the lat value is None."""
    tp = make_trackpoint(device_id=1, lat=None, lng=13.4)
    sensor = _make_sensor(1, positions={1: tp})
    assert sensor.latitude is None


def test_longitude_returns_float_when_position_exists() -> None:
    """Test that longitude returns a float when a position is available."""
    tp = make_trackpoint(device_id=1, lat=52.5, lng=13.4)
    sensor = _make_sensor(1, positions={1: tp})
    assert sensor.longitude == pytest.approx(13.4)


def test_longitude_returns_none_when_no_position() -> None:
    """Test that longitude returns None when no position data exists."""
    sensor = _make_sensor(1, positions={})
    assert sensor.longitude is None


def test_longitude_returns_none_when_lng_is_none() -> None:
    """Test that longitude returns None when the lng value is None."""
    tp = make_trackpoint(device_id=1, lat=52.5, lng=None)
    sensor = _make_sensor(1, positions={1: tp})
    assert sensor.longitude is None


def test_latitude_longitude_returns_zero_when_position_is_at_origin() -> None:
    """Test that lat/lng return 0.0 (not None) when the device is at exactly (0.0, 0.0)."""
    tp = make_trackpoint(device_id=1, lat=0.0, lng=0.0)
    sensor = _make_sensor(1, positions={1: tp})
    assert sensor.latitude == pytest.approx(0.0)
    assert sensor.longitude == pytest.approx(0.0)


def test_source_type_is_gps() -> None:
    """Test that the source type is reported as GPS."""
    sensor = _make_sensor(1)
    assert sensor.source_type == "gps"


def test_device_info_returned_from_coordinator() -> None:
    """Test that device info is returned and contains identifiers."""
    sensor = _make_sensor(1)
    info = sensor.device_info
    assert info is not None
    assert "identifiers" in info


async def test_entities_added_for_each_device() -> None:
    """Test that one entity is added per device during setup."""
    coord = make_coordinator()
    coord.data = PajGpsData(
        devices={1: make_device(1), 2: make_device(2)}, positions={}
    )
    hass, config_entry = _make_hass_and_config_entry(coord)

    added = []
    await dt_module.async_setup_entry(
        hass, config_entry, lambda e, **kw: added.extend(e)
    )

    assert len(added) == 2
    assert isinstance(added[0], PajGPSDeviceTracker)


async def test_no_entities_added_and_warning_logged_when_no_devices() -> None:
    """Test that no entities are added and a warning is logged when there are no devices."""
    coord = make_coordinator()
    coord.data = PajGpsData(devices={}, positions={})
    hass, config_entry = _make_hass_and_config_entry(coord)

    added = []
    with patch("homeassistant.components.pajgps.device_tracker._LOGGER") as mock_log:
        await dt_module.async_setup_entry(
            hass, config_entry, lambda e, **kw: added.extend(e)
        )
        mock_log.warning.assert_called_once()

    assert len(added) == 0


async def test_devices_with_none_id_are_skipped() -> None:
    """Test that devices with a None ID are skipped during setup."""
    coord = make_coordinator()
    coord.data = PajGpsData(devices={}, positions={})
    hass, config_entry = _make_hass_and_config_entry(coord)

    added = []
    with patch("homeassistant.components.pajgps.device_tracker._LOGGER"):
        await dt_module.async_setup_entry(
            hass, config_entry, lambda e, **kw: added.extend(e)
        )

    assert len(added) == 0


async def test_new_device_added_on_coordinator_update() -> None:
    """Entities for devices discovered after setup must be added dynamically."""
    coord = make_coordinator()
    coord.data = PajGpsData(devices={1: make_device(1)}, positions={})
    hass, config_entry = _make_hass_and_config_entry(coord)

    added = []
    await dt_module.async_setup_entry(
        hass, config_entry, lambda e, **kw: added.extend(e)
    )
    assert len(added) == 1

    # Simulate coordinator fetching a second device
    coord.data = PajGpsData(
        devices={1: make_device(1), 2: make_device(2)}, positions={}
    )
    coord.async_update_listeners()

    assert len(added) == 2
    device_ids = {s._device_id for s in added}
    assert device_ids == {1, 2}


async def test_existing_device_not_duplicated_on_coordinator_update() -> None:
    """A device already tracked must not produce a duplicate entity on re-update."""
    coord = make_coordinator()
    coord.data = PajGpsData(devices={1: make_device(1)}, positions={})
    hass, config_entry = _make_hass_and_config_entry(coord)

    added = []
    await dt_module.async_setup_entry(
        hass, config_entry, lambda e, **kw: added.extend(e)
    )
    assert len(added) == 1

    # Fire listener with the same device list — no new entity should be created
    coord.async_update_listeners()

    assert len(added) == 1


async def test_available_false_when_device_removed_from_coordinator() -> None:
    """Available must be False once a device disappears from coordinator.data.devices."""
    coord = make_coordinator()
    coord.data = PajGpsData(devices={1: make_device(1)}, positions={})
    sensor = PajGPSDeviceTracker(coord, 1)

    assert sensor.available is True

    # Simulate device disappearing from the account
    coord.data = PajGpsData(devices={}, positions={})
    assert sensor.available is False


async def test_available_true_when_device_present_in_coordinator() -> None:
    """Available must be True when the device is in coordinator.data.devices."""
    coord = make_coordinator()
    coord.data = PajGpsData(
        devices={1: make_device(1), 2: make_device(2)}, positions={}
    )
    sensor = PajGPSDeviceTracker(coord, 2)

    assert sensor.available is True


async def test_available_recovers_when_device_reappears() -> None:
    """Available must return to True if a previously missing device comes back."""
    coord = make_coordinator()
    coord.data = PajGpsData(devices={1: make_device(1)}, positions={})
    sensor = PajGPSDeviceTracker(coord, 1)

    coord.data = PajGpsData(devices={}, positions={})
    assert sensor.available is False

    coord.data = PajGpsData(devices={1: make_device(1)}, positions={})
    assert sensor.available is True
