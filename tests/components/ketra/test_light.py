"""Tests for the Ketra Light platform."""

import pytest

from homeassistant.components.ketra import DOMAIN as KETRA_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from .common import LIGHT_GROUP_ENTITY_ID, MockHub, setup_platform

from tests.async_mock import patch


@pytest.fixture(name="platform_common")
async def setup_light_platform(hass):
    """Set up platform."""
    hub = MockHub()

    async def patched_get_hub(*args, **kwargs):
        return hub

    with patch("aioketraapi.n4_hub.N4Hub.get_hub", new=patched_get_hub), patch(
        "homeassistant.components.ketra.KETRA_PLATFORMS", ["light"]
    ), patch("homeassistant.components.ketra.WEBSOCKET_RECONNECT_DELAY", 0.1):
        entry = await setup_platform(hass)
        cmn_plat = hass.data[KETRA_DOMAIN][entry.unique_id]["common_platform"]
        yield cmn_plat
        await cmn_plat.shutdown()


async def test_light_platform_creation(hass, platform_common):
    """Test platform creation."""
    assert len(platform_common.platforms) == 1
    state = hass.states.get(f"{LIGHT_DOMAIN}.{LIGHT_GROUP_ENTITY_ID}")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == LIGHT_GROUP_ENTITY_ID
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 179


async def test_light_turn_on(hass, platform_common):
    """Test turning on light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.{LIGHT_GROUP_ENTITY_ID}",
            "hs_color": [240, 100],
            "brightness": 255,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert platform_common.hub.group.state.power_on
    assert platform_common.hub.group.state.x_chromaticity == 0.136
    assert platform_common.hub.group.state.y_chromaticity == 0.04
    assert platform_common.hub.group.state.brightness == 1.0
    state = hass.states.get(f"{LIGHT_DOMAIN}.{LIGHT_GROUP_ENTITY_ID}")
    assert state.state == STATE_ON


async def test_light_turn_off(hass, platform_common):
    """Test turning off light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: f"{LIGHT_DOMAIN}.{LIGHT_GROUP_ENTITY_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert not platform_common.hub.group.state.power_on
    state = hass.states.get(f"{LIGHT_DOMAIN}.{LIGHT_GROUP_ENTITY_ID}")
    assert state.state == STATE_OFF
