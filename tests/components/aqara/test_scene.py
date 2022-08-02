"""Tests for the Aqara button device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNKNOWN,
    SERVICE_TURN_ON,
)


DEVICE_ID = "scene.daughter_room_all_off"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SCENE_DOMAIN)
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(DEVICE_ID)
        # print("=============test_entity_registry=============")
        # print(entry)
        assert entry.platform == "aqara"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the scene attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SCENE_DOMAIN)
        state = hass.states.get(DEVICE_ID)
        assert state.state == STATE_UNKNOWN
        print("====== test_attributes =====")
        print(state)


async def test_activate_scene(hass: HomeAssistant) -> None:
    """Test the scene can be active."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SCENE_DOMAIN)

        with patch("aqara_iot.AqaraHomeManager.trigger_scene") as mock_command:
            assert await hass.services.async_call(
                SCENE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()
