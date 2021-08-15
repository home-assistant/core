"""Aussie Broadband common helpers for tests."""
from unittest.mock import patch

from homeassistant.components.aussie_broadband import (
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DOMAIN as AUSSIE_BROADBAND_DOMAIN,
)
from homeassistant.components.aussie_broadband.const import ATTR_SERVICE_ID

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the Aussie Broadband platform."""
    mock_entry = MockConfigEntry(
        domain=AUSSIE_BROADBAND_DOMAIN,
        data={
            ATTR_USERNAME: "user@email.com",
            ATTR_PASSWORD: "password",
            ATTR_SERVICE_ID: "12345678",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aussie_broadband.PLATFORMS", [platform]
    ), patch("aussiebb.AussieBB.__init__", return_value=None):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
