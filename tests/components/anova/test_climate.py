"""Test the Anova climate platform."""
from unittest.mock import AsyncMock

from anova_wifi import AnovaApi
import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.components.anova import async_init_integration

entity_id = "climate.anova_precision_cooker"


@pytest.mark.parametrize(
    ("mode", "call_arg"), [(HVACMode.HEAT, "COOK"), (HVACMode.OFF, "IDLE")]
)
async def test_climate_set_mode(
    hass: HomeAssistant,
    anova_api: AnovaApi,
    anova_precision_cooker: AsyncMock,
    mode: HVACMode,
    call_arg: str,
) -> None:
    """Test setting the mode of the Anova climate."""
    await async_init_integration(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: mode},
        blocking=True,
    )
    assert anova_precision_cooker.set_mode.call_args[0][0] == call_arg


@pytest.mark.parametrize(
    ("mode", "call_arg"), [(HVACMode.HEAT, "COOK"), (HVACMode.OFF, "IDLE")]
)
async def test_set_mode_error(
    hass: HomeAssistant,
    anova_api: AnovaApi,
    anova_precision_cooker_setter_failure: AsyncMock,
    mode: HVACMode,
    call_arg: str,
) -> None:
    """Test that on error we raise HomeAssistantError."""
    await async_init_integration(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: mode},
            blocking=True,
        )
    assert anova_precision_cooker_setter_failure.set_mode.call_args[0][0] == call_arg


async def test_climate_set_temperature(
    hass: HomeAssistant, anova_api: AnovaApi, anova_precision_cooker: AsyncMock
) -> None:
    """Test setting the temperature of an Anova device."""
    await async_init_integration(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 88},
        blocking=True,
    )
    assert anova_precision_cooker.set_target_temperature.call_args[0][0] == 88


async def test_climate_set_temperature_error(
    hass: HomeAssistant,
    anova_api: AnovaApi,
    anova_precision_cooker_setter_failure: AsyncMock,
) -> None:
    """Test setting the temperature of an Anova device."""
    with pytest.raises(HomeAssistantError):
        await async_init_integration(hass)
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 88},
            blocking=True,
        )
        assert (
            anova_precision_cooker_setter_failure.set_target_temperature.call_args[0][0]
            == 88
        )


async def test_get_hvac_actions_maintaining(
    hass: HomeAssistant, anova_api: AnovaApi, anova_precision_cooker: AsyncMock
) -> None:
    """Test the hvac actions are correctly mapped."""
    anova_precision_cooker.status.binary_sensor.maintaining = True
    await async_init_integration(hass)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_get_hvac_actions_cooking(
    hass: HomeAssistant, anova_api: AnovaApi, anova_precision_cooker: AsyncMock
) -> None:
    """Test the hvac actions are correctly mapped."""
    anova_precision_cooker.status.binary_sensor.cooking = True
    await async_init_integration(hass)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING


async def test_get_hvac_actions_preheating(
    hass: HomeAssistant, anova_api: AnovaApi, anova_precision_cooker: AsyncMock
) -> None:
    """Test the hvac actions are correctly mapped."""
    anova_precision_cooker.status.binary_sensor.preheating = True
    await async_init_integration(hass)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
