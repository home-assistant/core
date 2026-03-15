"""Test the Casper Glow integration init."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_device_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady when BLE device is not found."""
    mock_config_entry.add_to_hass(hass)

    # Do not inject BLE info — device is not in the cache
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    result = await hass.config_entries.async_unload(config_entry.entry_id)

    assert result is True
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_coordinator_polls_on_advertisement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test that the coordinator polls device state when an advertisement is received."""
    mock_casper_glow.reset_mock()
    await hass.config_entries.async_reload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    mock_casper_glow.query_state.assert_called_once()
