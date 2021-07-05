"""Tests for the Freedompro climate."""

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_registry as er


async def test_climate_get_state(hass, init_integration):
    """Test states of the climate."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "climate.thermostat"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == "thermostat"

    assert state.attributes[ATTR_HVAC_MODES] == [
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
    ]

    assert state.attributes[ATTR_MIN_TEMP] == 7
    assert state.attributes[ATTR_MAX_TEMP] == 35
    assert state.attributes[ATTR_TEMPERATURE] == 14
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 14

    assert state.state == HVAC_MODE_HEAT

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*TWMYQKL3UVED4HSIIB9GXJWJZBQCXG-9VE-N2IUAIWI"
    )


async def test_climate_set_off(hass, init_integration):
    """Test set on of the climate."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "climate.thermostat"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == "thermostat"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*TWMYQKL3UVED4HSIIB9GXJWJZBQCXG-9VE-N2IUAIWI"
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVAC_MODE_HEAT


async def test_climate_set_temperature(hass, init_integration):
    """Test set on of the climate."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "climate.thermostat"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == "thermostat"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*TWMYQKL3UVED4HSIIB9GXJWJZBQCXG-9VE-N2IUAIWI"
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 14},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert hass.states.get(entity_id).attributes[ATTR_TEMPERATURE] == 14
