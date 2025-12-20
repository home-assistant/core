"""Test the Actron Air integration initialization."""

from unittest.mock import AsyncMock

from actron_neo_api import ActronAirAPIError, ActronAirAuthError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of entry."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.update_status = AsyncMock()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_error_on_get_systems(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails with ConfigEntryAuthFailed when authentication fails on get_ac_systems."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.get_ac_systems = AsyncMock(
        side_effect=ActronAirAuthError("Auth failed")
    )

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_auth_error_on_update_status(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails with ConfigEntryAuthFailed when authentication fails on update_status."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.update_status = AsyncMock(
        side_effect=ActronAirAuthError("Auth failed")
    )

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_api_error(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails with ConfigEntryNotReady when API error occurs."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.update_status = AsyncMock(
        side_effect=ActronAirAPIError("API error")
    )

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.update_status = AsyncMock()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
