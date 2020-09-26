"""Common methods used across the tests for ring devices."""
from homeassistant.components.ring import DOMAIN
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    MockConfigEntry(domain=DOMAIN, data={"username": "foo", "token": {}}).add_to_hass(
        hass
    )
    with patch("homeassistant.components.ring.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
