"""Tests for Ghost integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None


async def test_setup_entry_auth_error(
    hass: HomeAssistant, mock_ghost_api_auth_error: AsyncMock, mock_config_entry
) -> None:
    """Test setup fails with auth error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ghost.GhostAdminAPI",
        return_value=mock_ghost_api_auth_error,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_ghost_api_connection_error: AsyncMock, mock_config_entry
) -> None:
    """Test setup retries on connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ghost.GhostAdminAPI",
        return_value=mock_ghost_api_connection_error,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test unloading config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", return_value=mock_ghost_api
        ),
        patch(
            "homeassistant.components.ghost.coordinator.GhostAdminAPI",
            return_value=mock_ghost_api,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
