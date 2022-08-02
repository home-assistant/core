"""Tests for the Aqara button device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNKNOWN,
)


DEVICE_ID = "button.bed_control_lumi_12345"
DEVICE_UID = "Aqara.lumi.12345__4.7.85"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, BUTTON_DOMAIN)
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(DEVICE_ID)
        # print("=============test_entity_registry=============")
        # print(entry)
        assert entry.unique_id == DEVICE_UID  # "Aqara.lumi.12345__4.7.85"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the button attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, BUTTON_DOMAIN)
        state = hass.states.get(DEVICE_ID)
        assert state.state == STATE_UNKNOWN
        # print("====== test_attributes =====")
        print(state.state)


async def test_press(hass: HomeAssistant) -> None:
    """Test the button can be press."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, BUTTON_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_command:
            assert await hass.services.async_call(
                BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()

