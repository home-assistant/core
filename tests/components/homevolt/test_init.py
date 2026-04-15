"""Test the Homevolt init module."""

from __future__ import annotations

from unittest.mock import MagicMock

from homevolt import HomevoltAuthenticationError, HomevoltConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_homevolt_client.close_connection.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (
            HomevoltConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            HomevoltAuthenticationError("Authentication failed"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_config_entry_setup_failure(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the Homevolt configuration entry setup failures."""
    mock_homevolt_client.update_info.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is expected_state
