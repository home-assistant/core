"""Tests for the Omnilogic integration setup."""

from unittest.mock import patch

from omnilogic import LoginException

from homeassistant.components.omnilogic.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_login_failed(hass: HomeAssistant) -> None:
    """Test setup fails when logging in fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.omnilogic.OmniLogic.connect",
        side_effect=LoginException("Invalid credentials"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Login to OmniLogic failed"
