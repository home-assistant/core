"""Tests for the Roon integration setup."""

from unittest.mock import patch

from homeassistant.components.roon.const import CONF_ROON_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_failed(hass: HomeAssistant) -> None:
    """Test setup fails when the Roon server can't be set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_ROON_NAME: "Roon Core"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.roon.RoonServer.async_setup", return_value=False
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Failed to set up the Roon server Roon Core"
