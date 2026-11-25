"""Tests for WATERCryst entities."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .conftest import (
    BIOCAT_SERIAL,
    DEVICE_MANUFACTURER,
    DEVICE_NAME,
    DEVICE_TYPE_LINE,
    DEVICE_TYPE_NUMBER,
    DEVICE_TYPE_SERIES,
    FW_VERSION,
    HW_VERSION,
    SYSTEM_MAC_NORMALIZED,
)


async def test_initialization(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WATERCryst entity device info attributes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("sensor.ha_device_device_mode")

    assert entity_entry is not None
    assert entity_entry.unique_id == f"{BIOCAT_SERIAL}_mode_id"

    device_entry = device_registry.async_get(entity_entry.device_id)

    assert device_entry is not None
    assert device_entry.identifiers == {(DOMAIN, BIOCAT_SERIAL)}
    assert device_entry.connections == {(CONNECTION_NETWORK_MAC, SYSTEM_MAC_NORMALIZED)}
    assert device_entry.manufacturer == DEVICE_MANUFACTURER
    assert device_entry.model == f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}"
    assert device_entry.model_id == DEVICE_TYPE_NUMBER
    assert device_entry.name == DEVICE_NAME
    assert device_entry.serial_number == BIOCAT_SERIAL
    assert device_entry.sw_version == FW_VERSION
    assert device_entry.hw_version == HW_VERSION
    assert (
        device_entry.configuration_url
        == f"https://app.watercryst.com/devices/{BIOCAT_SERIAL}"
    )
