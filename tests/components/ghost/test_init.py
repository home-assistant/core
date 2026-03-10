"""Tests for Ghost integration setup."""

from unittest.mock import AsyncMock

from aioghost.exceptions import GhostAuthError, GhostConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (GhostAuthError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (GhostConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors."""
    mock_ghost_api.get_site.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test unloading config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
