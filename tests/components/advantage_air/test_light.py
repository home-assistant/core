"""Test the Advantage Air Switch Platform."""
from json import loads

from homeassistant.components.advantage_air.const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.helpers import entity_registry as er

from tests.components.advantage_air import (
    TEST_SET_LIGHT_URL,
    TEST_SET_RESPONSE,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)


async def test_light_async_setup_entry(hass, aioclient_mock):
    """Test light setup."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )
    aioclient_mock.get(
        TEST_SET_LIGHT_URL,
        text=TEST_SET_RESPONSE,
    )

    await add_mock_config(hass)

    registry = er.async_get(hass)

    assert len(aioclient_mock.mock_calls) == 1

    # Test Light Entity
    entity_id = "light.light_a"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-100"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 3
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLight"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["id"] == "100"
    assert data["state"] == ADVANTAGE_AIR_STATE_ON
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 5
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLight"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["id"] == "100"
    assert data["state"] == ADVANTAGE_AIR_STATE_OFF
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test Dimmable Light Entity
    entity_id = "light.light_b"

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-101"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id], ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    assert len(aioclient_mock.mock_calls) == 7
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLight"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["id"] == "101"
    assert data["value"] == 50
    assert data["state"] == ADVANTAGE_AIR_STATE_ON
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"
