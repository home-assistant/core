"""Tests for the Aqara switch device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)

DEVICE_ID = "climate.lumi1_6490c179afac_14_32_85"
DEVICE_UID = "Aqara.lumi1.6490c179afac__14.32.85"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, CLIMATE_DOMAIN)
        entity_registry = er.async_get(hass)

        entry = entity_registry.async_get(DEVICE_ID)
        # print(entry)
        assert entry.unique_id == DEVICE_UID


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the climate attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, CLIMATE_DOMAIN)

        state = hass.states.get(DEVICE_ID)
        # print("===========================================")
        # print(state)
        assert state.state == "cool"
        assert state.attributes.get("min_temp") == 7
        assert state.attributes.get("max_temp") == 35
        assert state.attributes.get("temperature") == 22.0


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test the climate can be turned on."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, CLIMATE_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_command:
            assert await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: DEVICE_ID},
                blocking=True,
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test the climate can be turned off."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, CLIMATE_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_command:
            assert await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: DEVICE_ID},
                blocking=True,
            )
            await hass.async_block_till_done()
            mock_command.assert_called_once()
