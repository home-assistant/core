"""Tests for the MotionMount Entity base."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import format_mac

from . import ZEROCONF_NAME

from tests.common import MockConfigEntry


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    mock_motionmount.is_authenticated = True
    mock_motionmount.error_status = 0
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "none"


async def test_entity_no_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    mock_motionmount.mac = b"\x00\x00\x00\x00\x00\x00"
    mock_motionmount.is_authenticated = True
    mock_motionmount.error_status = 0
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "none"


async def test_entity_rename(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_motionmount: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    mock_motionmount.is_authenticated = True
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    mac = format_mac(mock_motionmount.mac.hex())
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device
    assert device.name == ZEROCONF_NAME

    entity = hass.data["entity_components"]["sensor"].get_entity(
        "sensor.my_motionmount_error_status"
    )
    assert entity

    # Simulate the user changed the name of the device
    mock_motionmount.name = "Blub"
    entity.update_name()

    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device
    assert device.name == "Blub"
