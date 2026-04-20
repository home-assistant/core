"""Tests for the Russound RNET integration init."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_config_entry_setup_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test successful config entry setup."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test config entry not ready on connection failure."""
    mock_russound_client.connect.side_effect = TimeoutError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test config entry unload."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_serial_setup(
    hass: HomeAssistant,
    mock_serial_config_entry: MockConfigEntry,
    mock_russound_client: AsyncMock,
) -> None:
    """Test serial config entry setup."""
    await setup_integration(hass, mock_serial_config_entry)

    assert mock_serial_config_entry.state is ConfigEntryState.LOADED
