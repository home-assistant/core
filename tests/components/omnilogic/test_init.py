"""Tests for the Omnilogic integration setup."""

from unittest.mock import patch

from omnilogic import LoginException, OmniLogicException
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.omnilogic.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant


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

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_setup_connection_failed(hass: HomeAssistant) -> None:
    """Test setup is retried when the connection fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.omnilogic.OmniLogic.connect",
        side_effect=OmniLogicException("Failure getting token."),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()
