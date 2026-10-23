"""Tests for the UpCloud integration setup."""

from unittest.mock import patch

from upcloud_api import UpCloudAPIError

from homeassistant.components.upcloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_authentication_failed(hass: HomeAssistant) -> None:
    """Test setup fails when authentication fails."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )
    entry.add_to_hass(hass)

    with patch(
        "upcloud_api.CloudManager.authenticate",
        side_effect=UpCloudAPIError(
            error_code="AUTHENTICATION_FAILED",
            error_message="Authentication failed using the given username and password.",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Authentication with UpCloud failed"
