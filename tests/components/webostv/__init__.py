"""Tests for the WebOS TV integration."""
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.webostv.const import DOMAIN
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TV_NAME = "fake"
ENTITY_ID = f"{MP_DOMAIN}.{TV_NAME}"


async def setup_webostv(hass):
    """Initialize webostv and media_player for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_CLIENT_SECRET: "0123456789",
        },
        title=TV_NAME,
    )
    entry.add_to_hass(hass)

    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: "1.2.3.4"}},
    )
    await hass.async_block_till_done()

    return entry
