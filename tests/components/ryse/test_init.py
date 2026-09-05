"""Tests for RYSE init setup."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""
    assert setup_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_without_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the device is not seen by the bluetooth stack."""
    with patch(
        "homeassistant.components.ryse.async_ble_device_from_address",
        return_value=None,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
