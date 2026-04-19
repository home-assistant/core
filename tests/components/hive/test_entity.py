"""Tests for the Hive base entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.hive.const import DOMAIN
from homeassistant.components.hive.entity import HiveEntity
from homeassistant.helpers.device_registry import DeviceInfo


def _make_device(**overrides: Any) -> dict[str, Any]:
    """Return a representative Hive device payload for tests."""
    device: dict[str, Any] = {
        "haName": "Living Room Radiator Boost",
        "device_name": "Living Room Radiator",
        "hiveID": "hive-id-123",
        "hiveType": "Heating",
        "device_id": "device-id-456",
        "parentDevice": "parent-device-789",
        "deviceData": {
            "model": "SLR2",
            "manufacturer": "Hive",
            "version": "1.2.3",
            "online": True,
        },
    }
    device.update(overrides)
    return device


def _make_coordinator(hive: MagicMock | None = None) -> MagicMock:
    """Return a mock coordinator with sensible defaults."""
    coordinator = MagicMock()
    coordinator.hive = hive or MagicMock()
    coordinator.data = None
    coordinator.last_update_success = True
    return coordinator


@pytest.mark.parametrize(
    ("ha_name", "device_name", "expected"),
    [
        ("Living Room", "Living Room", None),
        ("Living Room Boost", "Living Room", "Boost"),
        ("Living Room ", "Living Room", None),
        ("Living Room   extra", "Living Room", "extra"),
        ("Unrelated Name", "Living Room", "Unrelated Name"),
        (None, "Living Room", None),
        ("Living Room Boost", None, None),
        ("", "Living Room", None),
    ],
)
def test_derive_entity_name(
    ha_name: str | None, device_name: str | None, expected: str | None
) -> None:
    """Test the suffix-derivation helper covers all branches."""
    assert HiveEntity._derive_entity_name(ha_name, device_name) == expected


def test_init_sets_expected_attributes() -> None:
    """Test that __init__ populates attributes from the device payload."""
    coordinator = _make_coordinator()
    device = _make_device()
    entity = HiveEntity(coordinator, device)
    assert entity.hive is coordinator.hive
    assert entity.device is device
    assert entity._attr_has_entity_name is True
    assert entity._attr_name == "Boost"
    assert entity._attr_unique_id == "hive-id-123-Heating"
    assert entity._attr_device_info == DeviceInfo(
        identifiers={(DOMAIN, "device-id-456")},
        model="SLR2",
        manufacturer="Hive",
        name="Living Room Radiator",
        sw_version="1.2.3",
        via_device=(DOMAIN, "parent-device-789"),
    )
    assert entity.attributes == {}


def test_init_name_none_when_ha_name_equals_device_name() -> None:
    """Test that _attr_name is None when haName matches device_name."""
    entity = HiveEntity(_make_coordinator(), _make_device(haName="Living Room Radiator"))
    assert entity._attr_name is None


def test_init_missing_ha_name_key() -> None:
    """Test that a missing haName key falls back to _attr_name None."""
    device = _make_device()
    device.pop("haName")
    entity = HiveEntity(_make_coordinator(), device)
    assert entity._attr_name is None


def test_available_true_when_coordinator_ok_and_device_online() -> None:
    """Test available returns True when coordinator succeeded and device is online."""
    coordinator = _make_coordinator()
    coordinator.last_update_success = True
    entity = HiveEntity(coordinator, _make_device())
    assert entity.available is True


def test_available_false_when_device_offline() -> None:
    """Test available returns False when device reports offline."""
    coordinator = _make_coordinator()
    coordinator.last_update_success = True
    device = _make_device()
    device["deviceData"]["online"] = False
    entity = HiveEntity(coordinator, device)
    assert entity.available is False


def test_available_false_when_coordinator_failed() -> None:
    """Test available returns False when the last coordinator update failed."""
    coordinator = _make_coordinator()
    coordinator.last_update_success = False
    entity = HiveEntity(coordinator, _make_device())
    assert entity.available is False


def test_handle_coordinator_update_refreshes_device() -> None:
    """Test that _handle_coordinator_update replaces self.device from coordinator data."""
    coordinator = _make_coordinator()
    device = _make_device()
    entity = HiveEntity(coordinator, device)
    entity.async_write_ha_state = MagicMock()
    updated_device = _make_device(hiveType="UpdatedType")
    coordinator.data = {"hive-id-123": updated_device}
    entity._handle_coordinator_update()
    assert entity.device is updated_device
    entity.async_write_ha_state.assert_called_once()


def test_handle_coordinator_update_keeps_device_when_no_data() -> None:
    """Test that _handle_coordinator_update retains existing device when data is None."""
    coordinator = _make_coordinator()
    device = _make_device()
    entity = HiveEntity(coordinator, device)
    entity.async_write_ha_state = MagicMock()
    coordinator.data = None
    entity._handle_coordinator_update()
    assert entity.device is device
    entity.async_write_ha_state.assert_called_once()
