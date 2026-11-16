"""Test the EnOcean integration."""

from unittest.mock import Mock, patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_device_not_connected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a config entry is not ready if the device is not connected."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.enocean.Gateway.start",
        side_effect=ConnectionError("Device not found"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_stops_gateway(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_gateway: Mock
) -> None:
    """Test that unloading the config entry stops the gateway."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_gateway.stop.assert_awaited_once()
