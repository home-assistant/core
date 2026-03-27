"""Test the EnOcean integration."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
