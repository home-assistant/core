"""Tests for the Ketra Scene platform."""

import pytest

from homeassistant.components.ketra import DOMAIN as KETRA_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, SERVICE_TURN_ON

from .common import SCENE_ENTITY_ID, MockHub, setup_platform

from tests.async_mock import patch


@pytest.fixture(name="platform_common")
async def setup_scene_platform(hass):
    """Set up platform."""

    hub = MockHub()

    async def patched_get_hub(*args, **kwargs):
        return hub

    with patch("aioketraapi.n4_hub.N4Hub.get_hub", new=patched_get_hub), patch(
        "homeassistant.components.ketra.KETRA_PLATFORMS", ["scene"]
    ), patch("homeassistant.components.ketra.WEBSOCKET_RECONNECT_DELAY", 0.1):
        entry = await setup_platform(hass)
        cmn_plat = hass.data[KETRA_DOMAIN][entry.unique_id]["common_platform"]
        yield cmn_plat
        await cmn_plat.shutdown()


async def test_scene_platform_creation(hass, platform_common):
    """Test platform creation."""
    assert len(platform_common.platforms) == 1
    state = hass.states.get(f"{SCENE_DOMAIN}.{SCENE_ENTITY_ID}")
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == SCENE_ENTITY_ID


async def test_scene_activation(hass, platform_common):
    """Test scene activation."""
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: f"{SCENE_DOMAIN}.{SCENE_ENTITY_ID}"},
        blocking=True,
    )
    await hass.async_block_till_done()
    platform_common.hub.button.activate.assert_called_once()
