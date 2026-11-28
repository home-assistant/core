"""Test the Rotarex init."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from rotarex_dimes_srg_api import InvalidAuth, RotarexConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test successful setup and unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_rotarex_api.login.assert_awaited_once()
    mock_rotarex_api.fetch_tanks.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (InvalidAuth, ConfigEntryState.SETUP_ERROR),
        (RotarexConnectionError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_login_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
    exception: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test login errors during setup."""
    mock_rotarex_api.login.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


@pytest.mark.parametrize("exception", [InvalidAuth, RotarexConnectionError])
async def test_setup_fetch_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
    exception: type[Exception],
) -> None:
    """Test errors fetching the tanks during setup are retried."""
    mock_rotarex_api.fetch_tanks.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
