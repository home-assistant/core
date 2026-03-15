"""Tests for the Leviton Decora Wi-Fi __init__ (config entry setup/unload)."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_decora_wifi: MagicMock,
) -> None:
    """Test config entry setup and unload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_decora_wifi: MagicMock,
) -> None:
    """Test config entry setup fails on auth error."""
    mock_decora_wifi.login.return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_decora_wifi: MagicMock,
) -> None:
    """Test config entry setup retries on connection error."""
    mock_decora_wifi.login.side_effect = ValueError("Cannot connect")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry_logout_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_decora_wifi: MagicMock,
    mock_person: MagicMock,
) -> None:
    """Test unload succeeds even if logout raises ValueError."""
    mock_person.logout.side_effect = ValueError("Logout failed")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_stop_event_logs_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_decora_wifi: MagicMock,
    mock_person: MagicMock,
) -> None:
    """Test that the HA stop event triggers a session logout."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_person.logout.assert_called_once_with(mock_decora_wifi)
