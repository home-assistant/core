"""Common methods used across tests for Abode."""
from unittest.mock import patch

from homeassistant.components.abode import DOMAIN as ABODE_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the Abode platform."""
    MockConfigEntry(
        domain=ABODE_DOMAIN, data={CONF_USERNAME: "foo", CONF_PASSWORD: "bar"}
    ).add_to_hass(hass)

    with patch("homeassistant.components.abode.ABODE_PLATFORMS", [platform]), patch(
        "abodepy.event_controller.sio"
    ):
        assert await async_setup_component(hass, ABODE_DOMAIN, {})
    await hass.async_block_till_done()
