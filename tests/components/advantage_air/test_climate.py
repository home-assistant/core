"""Test the Advantage Air Climate Platform."""
from json import loads

from homeassistant.components.advantage_air.climate import (
    ADVANTAGE_AIR_COOL_TARGET,
    ADVANTAGE_AIR_HEAT_TARGET,
    ADVANTAGE_AIR_MYAUTO,
    ADVANTAGE_AIR_MYAUTO_ENABLED,
    ADVANTAGE_AIR_MYTEMP_ENABLED,
    ADVANTAGE_AIR_SERVICE_SET_MYZONE,
    HASS_FAN_MODES,
    HASS_HVAC_MODES,
)
from homeassistant.components.advantage_air.const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.helpers import entity_registry as er

from tests.components.advantage_air import (
    TEST_SET_RESPONSE,
    TEST_SET_URL,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)


async def test_climate_async_setup_entry(hass, aioclient_mock):
    """Test climate platform."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )
    aioclient_mock.get(
        TEST_SET_URL,
        text=TEST_SET_RESPONSE,
    )
    await add_mock_config(hass)

    registry = er.async_get(hass)

    assert len(aioclient_mock.mock_calls) == 1

    # Test Climate Entity with MyZone
    entity_id = "climate.myzone"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.FAN_ONLY
    assert state.attributes.get(ATTR_MIN_TEMP) == 16
    assert state.attributes.get(ATTR_MAX_TEMP) == 32
    assert state.attributes.get(ATTR_TEMPERATURE) == 24
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1"

    # Test setting HVAC Mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 3
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["state"] == ADVANTAGE_AIR_STATE_ON
    assert data["ac1"]["info"]["mode"] == HASS_HVAC_MODES[HVACMode.FAN_ONLY]
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test Turning off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 5
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["state"] == ADVANTAGE_AIR_STATE_OFF
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test changing Fan Mode
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

    # Test changing Temperature
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

    # Test changing Preset
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: ADVANTAGE_AIR_MYAUTO},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 11
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"][ADVANTAGE_AIR_MYAUTO_ENABLED] is True
    assert data["ac1"]["info"][ADVANTAGE_AIR_MYTEMP_ENABLED] is False
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test MyTemp Climate Zone Entity
    entity_id = "climate.zone_open_with_sensor"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get(ATTR_MIN_TEMP) == 16
    assert state.attributes.get(ATTR_MAX_TEMP) == 32
    assert state.attributes.get(ATTR_TEMPERATURE) == 24
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == 25

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 13
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 15
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
    assert len(aioclient_mock.mock_calls) == 17
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test MyAuto Climate Entity
    entity_id = "climate.testname_myauto"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == 20
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == 24

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac3"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: [entity_id],
            ATTR_TARGET_TEMP_LOW: 21,
            ATTR_TARGET_TEMP_HIGH: 23,
        },
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 19
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["info"][ADVANTAGE_AIR_HEAT_TARGET] == 21
    assert data["ac3"]["info"][ADVANTAGE_AIR_COOL_TARGET] == 23
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test set_myair service
    entity_id = "climate.testname_zone_b"
    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_MYZONE,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    # assert len(aioclient_mock.mock_calls) == 21
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac2"]["info"]["myZone"] == 2
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
        {ATTR_ENTITY_ID: ["climate.myzone"], ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 2
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/setAircon"
