"""Tests for the Duco integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from duco.exceptions import DucoConnectionError, DucoError
from duco.models import BoardInfo

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a DucoConnectionError during board info fetch triggers a retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.duco.DucoClient",
        autospec=True,
    ) as mock_class:
        mock_class.return_value.async_get_board_info = AsyncMock(
            side_effect=DucoConnectionError("Connection refused")
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_duco_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a DucoError during board info fetch triggers a retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.duco.DucoClient",
        autospec=True,
    ) as mock_class:
        mock_class.return_value.async_get_board_info = AsyncMock(
            side_effect=DucoError("Unexpected API error")
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_nodes_fetch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_board_info: BoardInfo,
) -> None:
    """Test that a connection error during initial node fetch triggers a retry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.duco.DucoClient",
        autospec=True,
    ) as mock_class:
        mock_class.return_value.async_get_board_info = AsyncMock(
            return_value=mock_board_info
        )
        mock_class.return_value.async_get_nodes = AsyncMock(
            side_effect=DucoConnectionError("Connection refused")
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test successful setup of the Duco integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test unloading the Duco integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
