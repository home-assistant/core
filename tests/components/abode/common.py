"""Common methods used across tests for Abode."""
from unittest.mock import patch

from homeassistant.components.abode import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the Abode platform."""
    MockConfigEntry(
        domain=DOMAIN, data={"username": "foo", "password": "bar"}
    ).add_to_hass(hass)

    with patch("homeassistant.components.abode.ABODE_PLATFORMS", [platform]), patch(
        "abodepy.event_controller.sio"
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
