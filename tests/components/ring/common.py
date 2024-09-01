"""Common methods used across the tests for ring devices."""

from unittest.mock import patch

from homeassistant.components.ring import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platform: Platform) -> None:
    """Set up the ring platform and prerequisites."""
    MockConfigEntry(domain=DOMAIN, data={"username": "foo", "token": {}}).add_to_hass(
        hass
    )
    with patch("homeassistant.components.ring.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
