"""Test fixtures for Prowl."""

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN as PROWL_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

API_BASE_URL = "https://api.prowlapp.com/publicapi/"


@pytest.fixture
async def configure_prowl_through_yaml(hass: HomeAssistant):
    """Configure the notify domain with YAML for the Prowl platform."""
    await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"platform": PROWL_DOMAIN, "api_key": "f00f"},
            ]
        },
    )
    await hass.async_block_till_done()
