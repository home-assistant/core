"""Test the Advantage Air Climate Platform."""

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_OFF,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE

from tests.components.advantage_air import add_mock_config, api_response


async def test_climate_async_setup_entry(hass, aiohttp_raw_server, aiohttp_unused_port):
    """Test climate setup."""

    port = aiohttp_unused_port()
    server = await aiohttp_raw_server(api_response, port=port)
    await add_mock_config(hass, port)

    registry = await hass.helpers.entity_registry.async_get_registry()

    # Test Main Climate Entity
    entity_id = "climate.ac_one"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVAC_MODE_FAN_ONLY
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("current_temperature") is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_FAN_ONLY},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_FAN_MODE: FAN_OFF},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    # Test Climate Zone Entity
    entity_id = "climate.zone_open_with_sensor"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("measuredTemp") == 25
    assert state.attributes.get("setTemp") == 24

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_FAN_ONLY},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    await server.close()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 25},
        blocking=True,
    )
