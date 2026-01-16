"""Tests for the Tailscale coordinator."""

from unittest.mock import MagicMock

from homeassistant.components.tailscale.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_remove_stale_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale: MagicMock,
) -> None:
    """Test that devices removed from Tailscale are removed from device registry."""
    # Set up the integration with initial devices
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    
    # Verify initial devices are present (3 devices from fixtures)
    devices = dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
    assert len(devices) == 3
    
    # Simulate a device being removed from Tailscale (keep only 2 devices)
    mock_tailscale.devices.return_value = {
        "123456": mock_tailscale.devices.return_value["123456"],
        "123457": mock_tailscale.devices.return_value["123457"],
    }
    
    # Trigger an update
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    
    # Verify the stale device was removed
    devices = dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
    assert len(devices) == 2
    
    # Verify the correct devices remain
    remaining_device_names = {
        list(device.identifiers)[0][1] for device in devices
    }
    assert "123458" not in remaining_device_names
    assert "123456" in remaining_device_names
    assert "123457" in remaining_device_names

async def test_no_devices_removed_when_all_present(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale: MagicMock,
) -> None:
    """Test that no devices are removed when all Tailscale devices are still present."""
    # Set up the integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    
    # Verify initial devices
    devices_before = dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
    assert len(devices_before) == 3
    
    # Trigger an update (all devices still present)
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    
    # Verify no devices were removed
    devices_after = dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
    assert len(devices_after) == 3
