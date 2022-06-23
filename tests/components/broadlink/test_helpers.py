"""Tests for Broadlink helper functions."""
import pytest
import voluptuous as vol

from homeassistant.components.broadlink.helpers import (
    async_clean_registries,
    data_packet,
    mac_address,
)
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from tests.common import MockConfigEntry, mock_device_registry, mock_registry


async def test_padding(hass):
    """Verify that non padding strings are allowed."""
    assert data_packet("Jg") == b"&"
    assert data_packet("Jg=") == b"&"
    assert data_packet("Jg==") == b"&"


async def test_valid_mac_address(hass):
    """Test we convert a valid MAC address to bytes."""
    valid = [
        "A1B2C3D4E5F6",
        "a1b2c3d4e5f6",
        "A1B2-C3D4-E5F6",
        "a1b2-c3d4-e5f6",
        "A1B2.C3D4.E5F6",
        "a1b2.c3d4.e5f6",
        "A1-B2-C3-D4-E5-F6",
        "a1-b2-c3-d4-e5-f6",
        "A1:B2:C3:D4:E5:F6",
        "a1:b2:c3:d4:e5:f6",
    ]
    for mac in valid:
        assert mac_address(mac) == b"\xa1\xb2\xc3\xd4\xe5\xf6"


async def test_invalid_mac_address(hass):
    """Test we do not accept an invalid MAC address."""
    invalid = [
        None,
        123,
        ["a", "b", "c"],
        {"abc": "def"},
        "a1b2c3d4e5f",
        "a1b2.c3d4.e5f",
        "a1-b2-c3-d4-e5-f",
        "a1b2c3d4e5f66",
        "a1b2.c3d4.e5f66",
        "a1-b2-c3-d4-e5-f66",
        "a1b2c3d4e5fg",
        "a1b2.c3d4.e5fg",
        "a1-b2-c3-d4-e5-fg",
        "a1b.2c3d4.e5fg",
        "a1b-2-c3-d4-e5-fg",
    ]
    for mac in invalid:
        with pytest.raises((ValueError, vol.Invalid)):
            mac_address(mac)


async def test_registry_cleaner(hass):
    """Test that we clean up config entries properly."""
    config_entry = MockConfigEntry(domain="broadlink")
    config_entry.add_to_hass(hass)

    entity_registry = mock_registry(
        hass,
        {
            "button.kitchen1234": RegistryEntry(
                entity_id="button.kitchen1234",
                unique_id="1234",
                platform="broadlink",
                device_id="mock-dev-id",
                config_entry_id=config_entry.entry_id,
            ),
            "button.kitchen4321": RegistryEntry(
                entity_id="button.kitchen4321",
                unique_id="4321",
                platform="broadlink",
                device_id="mock-dev-id",
                config_entry_id=config_entry.entry_id,
            ),
        },
    )

    device_registry = mock_device_registry(
        hass,
        {
            "mock-dev-id": DeviceEntry(
                id="mock-dev-id",
                area_id="mock-area-id",
                config_entries={config_entry.entry_id},
            )
        },
    )

    async_clean_registries(hass, config_entry, {"1234", "4321"}, Platform.BUTTON)
    assert set(entity_registry.entities.keys()) == {
        "button.kitchen1234",
        "button.kitchen4321",
    }
    assert set(device_registry.devices.keys()) == {"mock-dev-id"}

    async_clean_registries(hass, config_entry, {"4321"}, Platform.BUTTON)
    assert set(entity_registry.entities.keys()) == {"button.kitchen4321"}
    assert set(device_registry.devices.keys()) == {"mock-dev-id"}

    async_clean_registries(hass, config_entry, {}, Platform.BUTTON)
    assert set(entity_registry.entities.keys()) == set()
    assert set(device_registry.devices.keys()) == set()
