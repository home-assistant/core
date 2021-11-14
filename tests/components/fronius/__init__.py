"""Tests for the Fronius integration."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_RESOURCE
from homeassistant.setup import async_setup_component

from .const import DOMAIN, MOCK_HOST


async def setup_fronius_integration(hass):
    """Create the Fronius integration."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                CONF_RESOURCE: MOCK_HOST,
            }
        },
    )
    await hass.async_block_till_done()
