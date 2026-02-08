"""Tests for WaterFurnace integration setup."""

from unittest.mock import Mock

from waterfurnace.waterfurnace import WFCredentialError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test setup fails with auth error."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Invalid credentials"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
