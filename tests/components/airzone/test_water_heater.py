"""The water heater tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.const import (
    API_ACS_ON,
    API_ACS_POWER_MODE,
    API_ACS_SET_POINT,
    API_DATA,
    API_SYSTEM_ID,
)
from aioairzone.exceptions import AirzoneError
import pytest

from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as WATER_HEATER_DOMAIN,
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterService,
    WaterHeaterServiceArgument,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .util import async_init_integration


async def test_airzone_create_water_heater(hass: HomeAssistant) -> None:
    """Test creation of water heater."""

    await async_init_integration(hass)

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.state == STATE_ECO
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 43
    assert state.attributes[ATTR_MAX_TEMP] == 75
    assert state.attributes[ATTR_MIN_TEMP] == 30
    assert state.attributes[ATTR_TEMPERATURE] == 45


async def test_airzone_water_heater_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning on/off."""

    await async_init_integration(hass)

    HVAC_MOCK = {
        API_DATA: {
            API_SYSTEM_ID: 0,
            API_ACS_ON: 0,
        }
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.TURN_OFF,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.state == STATE_OFF

    HVAC_MOCK = {
        API_DATA: {
            API_SYSTEM_ID: 0,
            API_ACS_ON: 1,
        }
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.TURN_ON,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.state == STATE_ECO


async def test_airzone_water_heater_set_operation(hass: HomeAssistant) -> None:
    """Test setting the Operation mode."""

    await async_init_integration(hass)

    HVAC_MOCK_1 = {
        API_DATA: {
            API_SYSTEM_ID: 0,
            API_ACS_ON: 0,
        }
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_1,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.state == STATE_OFF

    HVAC_MOCK_2 = {
        API_DATA: {
            API_SYSTEM_ID: 0,
            API_ACS_ON: 1,
            API_ACS_POWER_MODE: 1,
        }
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_2,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_PERFORMANCE,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.state == STATE_PERFORMANCE

    HVAC_MOCK_3 = {
        API_DATA: {
            API_SYSTEM_ID: 0,
            API_ACS_ON: 1,
            API_ACS_POWER_MODE: 0,
        }
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK_3,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_ECO,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.state == STATE_ECO


async def test_airzone_water_heater_set_temp(hass: HomeAssistant) -> None:
    """Test setting the target temperature."""

    HVAC_MOCK = {
        API_DATA: {
            API_SYSTEM_ID: 0,
            API_ACS_SET_POINT: 35,
        }
    }

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
                WaterHeaterServiceArgument.TEMPERATURE: 35,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.attributes[ATTR_TEMPERATURE] == 35


async def test_airzone_water_heater_set_temp_error(hass: HomeAssistant) -> None:
    """Test error when setting the target temperature."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
            side_effect=AirzoneError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_dhw",
                WaterHeaterServiceArgument.TEMPERATURE: 80,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_dhw")
    assert state.attributes[ATTR_TEMPERATURE] == 45
