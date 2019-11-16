"""Tests for the Sighthound integration."""

import homeassistant.components.image_processing as ip
from homeassistant.const import CONF_API_KEY
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    ip.DOMAIN: {
        "platform": "sighthound",
        CONF_API_KEY: "abc123",
        ip.CONF_SOURCE: {ip.CONF_ENTITY_ID: "camera.demo_camera"},
    },
    "camera": {"platform": "demo"},
}

VALID_ENTITY_ID = "image_processing.sighthound_demo_camera"


async def test_setup_platform(hass):
    """Set up platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)
