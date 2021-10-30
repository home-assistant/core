"""Test the Advantage Air Number Platform."""
from json import loads

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_registry as er

from tests.components.advantage_air import (
    TEST_SET_RESPONSE,
    TEST_SET_URL,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)


async def test_number_platform(hass, aioclient_mock):
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
    entity_id = "number.ac_one_time_to_on"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 0

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-timetoOn"

    value = 20
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: [entity_id], "value": value},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 3
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["countDownToOn"] == value
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"
