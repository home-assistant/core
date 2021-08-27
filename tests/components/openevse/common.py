"""Common methods used across the tests for OpenEVSE devices."""
from unittest.mock import patch

from homeassistant.components.openevse.const import CONF_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "Testing",
            CONF_HOST: "somefakehost.local",
            CONF_USERNAME: "fakeuser",
            CONF_PASSWORD: "fakepwd",
        },
    ).add_to_hass(hass)
    with patch("homeassistant.components.openevse.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
