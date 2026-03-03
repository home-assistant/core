"""Test the Cosa integration init."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.cosa.api import CosaAuthError, CosaConnectionError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cosa_api: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cosa_api: MagicMock,
) -> None:
    """Test config entry auth failed on invalid credentials."""
    mock_cosa_api.async_check_connection = AsyncMock(
        side_effect=CosaAuthError("Invalid credentials")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cosa_api: MagicMock,
) -> None:
    """Test config entry not ready on connection failure."""
    mock_cosa_api.async_check_connection = AsyncMock(
        side_effect=CosaConnectionError("Connection refused")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_endpoints(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cosa_api: MagicMock,
) -> None:
    """Test config entry not ready when no endpoints found."""
    mock_cosa_api.async_get_endpoints = AsyncMock(return_value=[])
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cosa_api: MagicMock,
) -> None:
    """Test successful unload of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
