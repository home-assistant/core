"""Test switch platform for Swing2Sleep Smarla integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connection
) -> None:
    """Test init invalid authentication behavior."""
    # Add the mock entry to hass
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        mock_connection, "refresh_token", new=AsyncMock(return_value=False)
    ):
        # Set up the platform
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
