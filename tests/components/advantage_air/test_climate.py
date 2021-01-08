"""Test the Advantage Air Climate Platform."""

from json import loads

from homeassistant.components.advantage_air.climate import (
    HASS_FAN_MODES,
    HASS_HVAC_MODES,
)
from homeassistant.components.advantage_air.const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
)
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_LOW,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_OFF,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE

from tests.components.advantage_air import (
    TEST_SET_RESPONSE,
    TEST_SET_URL,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)


async def test_climate_async_setup_entry(hass, aioclient_mock):
    """Test climate setup."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )
    aioclient_mock.get(
        TEST_SET_URL,
        text=TEST_SET_RESPONSE,
    )
    await add_mock_config(hass)

    registry = await hass.helpers.entity_registry.async_get_registry()

    assert len(aioclient_mock.mock_calls) == 1

    # Test Main Climate Entity
    entity_id = "climate.ac_one"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVAC_MODE_FAN_ONLY
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("temperature") == 24
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
    assert len(aioclient_mock.mock_calls) == 3
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["state"] == ADVANTAGE_AIR_STATE_ON
    assert data["ac1"]["info"]["mode"] == HASS_HVAC_MODES[HVAC_MODE_FAN_ONLY]
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 5
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["state"] == ADVANTAGE_AIR_STATE_OFF
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 7
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["fan"] == HASS_FAN_MODES[FAN_LOW]
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 9
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["setTemp"] == 25
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test Climate Zone Entity
    entity_id = "climate.zone_open_with_sensor"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("min_temp") == 16
    assert state.attributes.get("max_temp") == 32
    assert state.attributes.get("temperature") == 24
    assert state.attributes.get("current_temperature") == 25

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_FAN_ONLY},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 11
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 13
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 15
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"


async def test_climate_async_failed_update(hass, aioclient_mock):
    """Test climate change failure."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )
    aioclient_mock.get(
        TEST_SET_URL,
        exc=SyntaxError,
    )
    await add_mock_config(hass)

    assert len(aioclient_mock.mock_calls) == 1

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ["climate.ac_one"], ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 2
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/setAircon"
