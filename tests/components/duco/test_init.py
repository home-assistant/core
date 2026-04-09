"""Tests for the Duco integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError, DucoError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("method", "exception", "expected_state"),
    [
        (
            "async_get_board_info",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "async_get_board_info",
            DucoError("Unexpected API error"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "async_get_nodes",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    method: str,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test that fetch errors during setup result in the correct state."""
    getattr(mock_duco_client, method).side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("mock_duco_client")
async def test_setup_entry_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful setup of the Duco integration."""
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the Duco integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
