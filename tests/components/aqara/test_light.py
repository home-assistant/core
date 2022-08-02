"""Tests for the Aqara light device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)

DEVICE_ID = "light.ke_ting_xi_ding_deng_lumi_4cf8cdf3c76019a"
DEVICE_UID = "Aqara.lumi.4cf8cdf3c76019a__4.1.85"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        with patch("aqara_iot.AqaraOpenMQ.start") as mock_mq_start:

            await setup_platform(hass, LIGHT_DOMAIN)
            entity_registry = er.async_get(hass)

            entry = entity_registry.async_get(DEVICE_ID)
            print(entry)
            assert entry.unique_id == DEVICE_UID


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the light attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        with patch("aqara_iot.AqaraOpenMQ.start") as mock_mq_start:

            await setup_platform(hass, LIGHT_DOMAIN)

            state = hass.states.get(DEVICE_ID)
            print("===========================================")
            print(state)
            assert state.state == STATE_ON


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test the light can be turned on."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, LIGHT_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_light_on:
            assert await hass.services.async_call(
                LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
            )
            await hass.async_block_till_done()
            mock_light_on.assert_called_once()


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test the light can be turned off."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, LIGHT_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_light_off:
            assert await hass.services.async_call(
                LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
            )
            await hass.async_block_till_done()
            mock_light_off.assert_called_once()
