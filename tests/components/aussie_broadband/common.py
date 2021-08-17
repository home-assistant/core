"""Aussie Broadband common helpers for tests."""
from unittest.mock import patch

from homeassistant.components.aussie_broadband import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN as AUSSIE_BROADBAND_DOMAIN,
)
from homeassistant.components.aussie_broadband.const import CONF_SERVICE_ID

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the Aussie Broadband platform."""
    mock_entry = MockConfigEntry(
        domain=AUSSIE_BROADBAND_DOMAIN,
        data={
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_SERVICE_ID: "12345678",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aussie_broadband.PLATFORMS", [platform]
    ), patch("aussiebb.AussieBB.__init__", return_value=None):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
