"""The water heater tests for the Airzone Cloud platform."""

from unittest.mock import patch

from aioairzone_cloud.exceptions import AirzoneCloudError
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

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 45.5
    assert state.attributes[ATTR_MAX_TEMP] == 60
    assert state.attributes[ATTR_MIN_TEMP] == 40
    assert state.attributes[ATTR_TEMPERATURE] == 48


async def test_airzone_water_heater_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning on/off."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.TURN_ON,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.state == STATE_ECO

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.TURN_OFF,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.state == STATE_OFF


async def test_airzone_water_heater_set_operation(hass: HomeAssistant) -> None:
    """Test setting the Operation mode."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_ECO,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.state == STATE_ECO

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_PERFORMANCE,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.state == STATE_PERFORMANCE

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_OPERATION_MODE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.state == STATE_OFF


async def test_airzone_water_heater_set_temp(hass: HomeAssistant) -> None:
    """Test setting the target temperature."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.attributes[ATTR_TEMPERATURE] == 50


async def test_airzone_water_heater_set_temp_error(hass: HomeAssistant) -> None:
    """Test error when setting the target temperature."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
            side_effect=AirzoneCloudError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WaterHeaterService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: "water_heater.airzone_cloud_dhw",
                WaterHeaterServiceArgument.TEMPERATURE: 80,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.airzone_cloud_dhw")
    assert state.attributes[ATTR_TEMPERATURE] == 48
