"""Tests for the WattTime integration setup."""

from unittest.mock import patch

from aiowatttime.errors import WattTimeError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_authentication_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup fails on an error while authenticating."""
    with patch(
        "homeassistant.components.watttime.Client.async_login",
        side_effect=WattTimeError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "Error while authenticating with WattTime"
