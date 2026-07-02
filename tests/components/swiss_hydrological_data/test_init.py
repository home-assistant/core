"""Tests for Swiss Hydrological Data integration setup."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            ConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_swiss_hydro_data: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors."""
    mock_swiss_hydro_data.get_station.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant,
    mock_swiss_hydro_data: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
