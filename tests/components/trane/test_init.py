"""Tests for the Trane Local integration setup."""

from unittest.mock import MagicMock

from steamloop import AuthenticationError, SteamloopConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup retries on connection error."""
    mock_connection.connect.side_effect = SteamloopConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup fails on authentication error."""
    mock_connection.login.side_effect = AuthenticationError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test setup retries on timeout."""
    mock_connection.connect.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
