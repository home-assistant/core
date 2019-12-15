"""Common methods used across the tests for ring devices."""
from homeassistant.components.ring import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.setup import async_setup_component


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    config = {
        DOMAIN: {CONF_USERNAME: "foo", CONF_PASSWORD: "bar", CONF_SCAN_INTERVAL: 1000},
        platform: {"platform": DOMAIN},
    }
    assert await async_setup_component(hass, platform, config)
    await hass.async_block_till_done()
