"""Tests for the Aqara binary sensor device."""
from unittest.mock import patch
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.core import HomeAssistant
import aqara_iot.openmq
from .common import mock_start

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_ON,
)


DEVICE_ID = "binary_sensor.chu_fang_lou_shui_lumi_4cf8cdf3c74ee7c"
DEVICE_UID = "Aqara.lumi.4cf8cdf3c74ee7c__3.1.85"
DEVICE_ID_2 = "binary_sensor.ren_ti_chuan_gan_qi_lumi_4cf8cdf3c75266a"


# async def test_entity_registry(hass: HomeAssistant) -> None:
#     """Tests that the devices are registered in the entity registry."""
#     await setup_platform(hass, BINARY_SENSOR_DOMAIN)
#     entity_registry = er.async_get(hass)

#     entry = entity_registry.async_get(DEVICE_ID)
#     print(entry)
#     assert entry.unique_id == DEVICE_UID


# async def test_attributes(hass: HomeAssistant) -> None:
#     """Test the switch attributes are correct."""
#     await setup_platform(hass, BINARY_SENSOR_DOMAIN)

#     state = hass.states.get(DEVICE_ID_2)
#     print("===========================================")
#     print(state)
#     assert state.state == STATE_ON
#     assert state.attributes.get(ATTR_DEVICE_CLASS) == "motion"
#     # print("=============== test_attributes ============================")
#     # print(state)
#     # print(state.attributes)
#     # print("===========================================================")


async def test_entity_registry(hass):
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, BINARY_SENSOR_DOMAIN)
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get(DEVICE_ID)
        assert entry
        assert entry.unique_id == DEVICE_UID
        assert entry.platform == "aqara"
        # print("=============== test_entity_registry ============================")
        # print(entry)
        # await hass.async_block_till_done()

        state = hass.states.get(DEVICE_ID_2)
        assert state.state == STATE_ON
        assert state.attributes.get(ATTR_DEVICE_CLASS) == "motion"
        # print("=============== test_attributes ============================")
        # print(state)
        # print(state.attributes)
        # print("===========================================================")


async def test_attributes(hass):
    """Test the binary sensor attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, BINARY_SENSOR_DOMAIN)
        state = hass.states.get(DEVICE_ID_2)
        # assert state.state == STATE_ON
        # assert state.attributes.get(ATTR_DEVICE_CLASS) == "motion"
        # # print("=============== test_attributes ============================")
        # # print(state)
        # # print(state.attributes)
        # # print("===========================================================")
        # await hass.async_block_till_done()
