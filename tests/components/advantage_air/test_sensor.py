"""Test the Advantage Air Sensor Platform."""
from datetime import timedelta
from json import loads

from homeassistant.components.advantage_air.const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from homeassistant.components.advantage_air.sensor import (
    ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
    ADVANTAGE_AIR_SET_COUNTDOWN_VALUE,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from . import (
    TEST_SET_RESPONSE,
    TEST_SET_URL,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor_platform(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sensor platform."""

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

    # Test First TimeToOn Sensor
    entity_id = "sensor.ac_one_time_to_on"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 0

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-timetoOn"

    value = 20
    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {ATTR_ENTITY_ID: [entity_id], ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: value},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 3
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["countDownToOn"] == value
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test First TimeToOff Sensor
    entity_id = "sensor.ac_one_time_to_off"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 10

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-timetoOff"

    value = 0
    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {ATTR_ENTITY_ID: [entity_id], ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: value},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 5
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["countDownToOff"] == value
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test First Zone Vent Sensor
    entity_id = "sensor.ac_one_zone_open_with_sensor_vent"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 100

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-vent"

    # Test Second Zone Vent Sensor
    entity_id = "sensor.ac_one_zone_closed_with_sensor_vent"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 0

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z02-vent"

    # Test First Zone Signal Sensor
    entity_id = "sensor.ac_one_zone_open_with_sensor_signal"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 40

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-signal"

    # Test Second Zone Signal Sensor
    entity_id = "sensor.ac_one_zone_closed_with_sensor_signal"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 10

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z02-signal"

    # Test First Zone Temp Sensor (disabled by default)
    entity_id = "sensor.ac_one_zone_open_with_sensor_temperature"

    assert not hass.states.get(entity_id)

    registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 25

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-temp"
