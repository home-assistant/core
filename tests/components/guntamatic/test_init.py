"""Test the Guntamatic integration setup."""

from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test successful setup of the integration."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (
            requests.exceptions.ConnectionError("Cannot connect"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup fails correctly for different error types."""
    mock_heater.parse_data.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state
