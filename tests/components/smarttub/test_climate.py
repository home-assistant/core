"""Test the SmartTub climate platform."""

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_HEAT,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.smarttub.const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)


async def test_thermostat(coordinator, spa, hass, config_entry):
    """Test the thermostat entity."""

    spa.get_status.return_value = {
        "heater": "ON",
        "water": {
            "temperature": 38,
        },
        "setTemperature": 39,
    }
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"climate.{spa.brand}_{spa.model}_thermostat"
    state = hass.states.get(entity_id)
    assert state

    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    spa.get_status.return_value["heater"] = "OFF"
    await hass.helpers.entity_component.async_update_entity(entity_id)
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE

    assert set(state.attributes[ATTR_HVAC_MODES]) == {HVAC_MODE_HEAT}
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORT_TARGET_TEMPERATURE
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 38
    assert state.attributes[ATTR_TEMPERATURE] == 39
    assert state.attributes[ATTR_MAX_TEMP] == DEFAULT_MAX_TEMP
    assert state.attributes[ATTR_MIN_TEMP] == DEFAULT_MIN_TEMP

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 37},
        blocking=True,
    )
    spa.set_temperature.assert_called_with(37)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        blocking=True,
    )
    # does nothing
