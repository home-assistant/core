"""Tests for the Crownstone integration setup."""

from unittest.mock import AsyncMock, patch

from crownstone_cloud.exceptions import CrownstoneAuthenticationError

from homeassistant.components.crownstone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_authentication_error(hass: HomeAssistant) -> None:
    """Test setup fails when authentication with the cloud fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "example@homeassistant.com", CONF_PASSWORD: "secret"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.crownstone.entry_manager.CrownstoneCloud.async_initialize",
        AsyncMock(
            side_effect=CrownstoneAuthenticationError(exception_type="LOGIN_FAILED")
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Authentication with the Crownstone cloud failed"
