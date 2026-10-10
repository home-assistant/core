"""Tests for the Hanna Instruments integration setup."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_hanna_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    mock_hanna_client.get_devices.return_value = [{"DID": "pool", "name": "Pool"}]
    mock_hanna_client.get_last_device_reading.return_value = {
        "DID": "pool",
        "messages": {"parameters": [{"name": "ph", "value": 7.2}]},
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
