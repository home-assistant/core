"""Tests for KEBA P40 setup and teardown."""

from unittest.mock import AsyncMock

from keba_kecontact_p40 import KebaP40AuthError, KebaP40ConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_client")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_connection_error_retries(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection error puts the entry in SETUP_RETRY."""
    mock_client.get_wallbox.side_effect = KebaP40ConnectionError
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an auth error puts the entry in SETUP_ERROR."""
    mock_client.get_wallbox.side_effect = KebaP40AuthError
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
