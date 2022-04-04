"""The climate tests for the Airzone platform."""

from unittest.mock import patch

from aioairzone.common import OperationMode
from aioairzone.const import (
    API_DATA,
    API_MODE,
    API_ON,
    API_SET_POINT,
    API_SYSTEM_ID,
    API_ZONE_ID,
)
from aioairzone.exceptions import AirzoneError
import pytest

from homeassistant.components.airzone.const import API_TEMPERATURE_STEP
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .util import async_init_integration


async def test_airzone_create_climates(hass: HomeAssistant) -> None:
    """Test creation of climates."""

    await async_init_integration(hass)

    state = hass.states.get("climate.despacho")
    assert state.state == HVAC_MODE_OFF
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 36
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 21.2
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_OFF
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVAC_MODE_OFF,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_DRY,
    ]
    assert state.attributes.get(ATTR_MAX_TEMP) == 30
    assert state.attributes.get(ATTR_MIN_TEMP) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_STEP) == API_TEMPERATURE_STEP
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.4

    state = hass.states.get("climate.dorm_1")
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 35
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 20.8
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_IDLE
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVAC_MODE_OFF,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_DRY,
    ]
    assert state.attributes.get(ATTR_MAX_TEMP) == 30
    assert state.attributes.get(ATTR_MIN_TEMP) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_STEP) == API_TEMPERATURE_STEP
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.3

    state = hass.states.get("climate.dorm_2")
    assert state.state == HVAC_MODE_OFF
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 40
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 20.5
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_OFF
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVAC_MODE_OFF,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_DRY,
    ]
    assert state.attributes.get(ATTR_MAX_TEMP) == 30
    assert state.attributes.get(ATTR_MIN_TEMP) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_STEP) == API_TEMPERATURE_STEP
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.5

    state = hass.states.get("climate.dorm_ppal")
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 39
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 21.1
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_HEAT
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVAC_MODE_OFF,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_DRY,
    ]
    assert state.attributes.get(ATTR_MAX_TEMP) == 30
    assert state.attributes.get(ATTR_MIN_TEMP) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_STEP) == API_TEMPERATURE_STEP
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.2

    state = hass.states.get("climate.salon")
    assert state.state == HVAC_MODE_OFF
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 34
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 19.6
    assert state.attributes.get(ATTR_HVAC_ACTION) == CURRENT_HVAC_OFF
    assert state.attributes.get(ATTR_HVAC_MODES) == [
        HVAC_MODE_OFF,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_DRY,
    ]
    assert state.attributes.get(ATTR_MAX_TEMP) == 30
    assert state.attributes.get(ATTR_MIN_TEMP) == 15
    assert state.attributes.get(ATTR_TARGET_TEMP_STEP) == API_TEMPERATURE_STEP
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.1


async def test_airzone_climate_set_hvac_mode(hass: HomeAssistant) -> None:
    """Test setting the HVAC mode."""

    await async_init_integration(hass)

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_MODE: OperationMode.COOLING.value,
                API_ON: 1,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.http_request",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVAC_MODE_COOL,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVAC_MODE_COOL

    HVAC_MOCK_2 = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 1,
                API_ON: 0,
            }
        ]
    }
    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.http_request",
        return_value=HVAC_MOCK_2,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVAC_MODE_OFF,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVAC_MODE_OFF


async def test_airzone_climate_set_hvac_slave_error(hass: HomeAssistant) -> None:
    """Test setting the HVAC mode for a slave zone."""

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 5,
                API_ON: 1,
            }
        ]
    }

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.http_request",
        return_value=HVAC_MOCK,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.dorm_2",
                ATTR_HVAC_MODE: HVAC_MODE_COOL,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dorm_2")
    assert state.state == HVAC_MODE_OFF


async def test_airzone_climate_set_temp(hass: HomeAssistant) -> None:
    """Test setting the target temperature."""

    HVAC_MOCK = {
        API_DATA: [
            {
                API_SYSTEM_ID: 1,
                API_ZONE_ID: 5,
                API_SET_POINT: 20.5,
            }
        ]
    }

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.http_request",
        return_value=HVAC_MOCK,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.dorm_2",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dorm_2")
    assert state.attributes.get(ATTR_TEMPERATURE) == 20.5


async def test_airzone_climate_set_temp_error(hass: HomeAssistant) -> None:
    """Test error when setting the target temperature."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.put_hvac",
        side_effect=AirzoneError,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.dorm_2",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dorm_2")
    assert state.attributes.get(ATTR_TEMPERATURE) == 19.5
