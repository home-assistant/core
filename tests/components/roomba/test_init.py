"""Tests for the Roomba integration setup."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when no connection data is returned."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.roomba.RoombaFactory.create_roomba"),
        patch(
            "homeassistant.components.roomba.async_connect_or_timeout",
            return_value={},
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == "Failed to connect to Roomba at 192.168.0.30"
