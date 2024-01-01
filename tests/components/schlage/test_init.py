"""Tests for the Schlage integration."""

from unittest.mock import Mock, patch

from pycognito.exceptions import WarrantException
from pyschlage.exceptions import Error, NotAuthorizedError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@patch(
    "pyschlage.Auth",
    side_effect=WarrantException,
)
async def test_auth_failed(
    mock_auth: Mock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test failed auth on setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_auth.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_update_data_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
) -> None:
    """Test that we properly handle API errors."""
    mock_schlage.locks.side_effect = Error
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_schlage.locks.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_data_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
) -> None:
    """Test that we properly handle API errors."""
    mock_schlage.locks.side_effect = NotAuthorizedError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_schlage.locks.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_update_data_get_logs_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
    mock_lock: Mock,
) -> None:
    """Test that we properly handle API errors."""
    mock_schlage.locks.return_value = [mock_lock]
    mock_lock.logs.reset_mock()
    mock_lock.logs.side_effect = NotAuthorizedError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_schlage.locks.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
) -> None:
    """Test the Schlage configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
