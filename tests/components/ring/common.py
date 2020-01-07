"""Common methods used across the tests for ring devices."""
from homeassistant.components.ring import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    MockConfigEntry(domain=DOMAIN, data={"username": "foo"}).add_to_hass(hass)
    assert await async_setup_component(hass, platform, {platform: {"platform": DOMAIN}})
    await hass.async_block_till_done()
