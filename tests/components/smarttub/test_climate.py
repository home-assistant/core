"""Test the SmartTub climate platform."""

import smarttub

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.smarttub.const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant

from . import trigger_update


async def test_thermostat_state(
    spa, spa_state, setup_entry, hass: HomeAssistant
) -> None:
    """Test the thermostat entity initial state and attributes."""
    entity_id = f"climate.{spa.brand}_{spa.model}_thermostat"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert set(state.attributes[ATTR_HVAC_MODES]) == {HVACMode.HEAT}
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 38
    assert state.attributes[ATTR_TEMPERATURE] == 39
    assert state.attributes[ATTR_MAX_TEMP] == DEFAULT_MAX_TEMP
    assert state.attributes[ATTR_MIN_TEMP] == DEFAULT_MIN_TEMP
    assert state.attributes[ATTR_PRESET_MODES] == ["none", "eco", "day", "ready"]
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_NONE


async def test_thermostat_hvac_action_update(
    spa, spa_state, setup_entry, hass: HomeAssistant
) -> None:
    """Test the thermostat HVAC action transitions from heating to idle."""
    entity_id = f"climate.{spa.brand}_{spa.model}_thermostat"
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    spa_state.heater = "OFF"
    await trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_thermostat_set_temperature(
    spa, setup_entry, hass: HomeAssistant
) -> None:
    """Test setting the target temperature."""
    entity_id = f"climate.{spa.brand}_{spa.model}_thermostat"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 37},
        blocking=True,
    )
    spa.set_temperature.assert_called_with(37)


async def test_thermostat_set_preset_mode(
    spa, spa_state, setup_entry, hass: HomeAssistant
) -> None:
    """Test setting a preset mode updates state correctly."""
    entity_id = f"climate.{spa.brand}_{spa.model}_thermostat"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    spa.set_heat_mode.assert_called_with(smarttub.Spa.HeatMode.ECONOMY)

    spa_state.heat_mode = smarttub.Spa.HeatMode.ECONOMY
    await trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_PRESET_MODE) == PRESET_ECO


async def test_thermostat_api_error(spa, setup_entry, hass: HomeAssistant) -> None:
    """Test that an API error during update does not raise."""
    spa.get_status_full.side_effect = smarttub.APIError
    await trigger_update(hass)
    # should not fail
