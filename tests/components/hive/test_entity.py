"""Tests for the Hive base entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hive.const import DOMAIN
from homeassistant.components.hive.entity import HiveEntity
from homeassistant.core import HomeAssistant
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
        },
    }
    device.update(overrides)
    return device


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
    hive = AsyncMock()
    device = _make_device()

    entity = HiveEntity(hive, device)

    assert entity.hive is hive
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
    entity = HiveEntity(
        AsyncMock(),
        _make_device(haName="Living Room Radiator"),
    )

    assert entity._attr_name is None


def test_init_missing_ha_name_key() -> None:
    """Test that a missing haName key falls back to _attr_name None."""
    device = _make_device()
    device.pop("haName")

    entity = HiveEntity(AsyncMock(), device)

    assert entity._attr_name is None


async def test_async_added_to_hass_registers_dispatcher(
    hass: HomeAssistant,
) -> None:
    """Test dispatcher registration and async_on_remove wiring."""
    entity = HiveEntity(AsyncMock(), _make_device())
    entity.hass = hass
    entity.async_on_remove = MagicMock()

    unsub = MagicMock()
    with patch(
        "homeassistant.components.hive.entity.async_dispatcher_connect",
        return_value=unsub,
    ) as mock_connect:
        await entity.async_added_to_hass()

    mock_connect.assert_called_once_with(hass, DOMAIN, entity.async_write_ha_state)
    entity.async_on_remove.assert_called_once_with(unsub)
