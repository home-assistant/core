"""Aussie Broadband common helpers for tests."""
from unittest.mock import patch

from homeassistant.components.aussie_broadband.const import (
    CONF_SERVICES,
    DOMAIN as AUSSIE_BROADBAND_DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

from tests.common import MockConfigEntry

FAKE_SERVICES = [
    {
        "service_id": "12345678",
        "description": "Fake ABB NBN Service",
        "type": "NBN",
        "name": "NBN",
    },
    {
        "service_id": "87654321",
        "description": "Fake ABB Mobile Service",
        "type": "PhoneMobile",
        "name": "Mobile",
    },
]

FAKE_DATA = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def setup_platform(hass, platforms=[], side_effect=None, usage={}):
    """Set up the Aussie Broadband platform."""
    mock_entry = MockConfigEntry(
        domain=AUSSIE_BROADBAND_DOMAIN,
        data=FAKE_DATA,
        options={CONF_SERVICES: ["12345678", "87654321"], CONF_SCAN_INTERVAL: 30},
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.aussie_broadband.PLATFORMS", platforms), patch(
        "aussiebb.asyncio.AussieBB.__init__", return_value=None
    ), patch(
        "aussiebb.asyncio.AussieBB.login",
        return_value=True,
        side_effect=side_effect,
    ), patch(
        "aussiebb.asyncio.AussieBB.get_services",
        return_value=FAKE_SERVICES,
        side_effect=side_effect,
    ), patch(
        "aussiebb.asyncio.AussieBB.get_usage", return_value=usage
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
