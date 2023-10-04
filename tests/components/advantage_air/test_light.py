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
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    TEST_SET_LIGHT_URL,
    TEST_SET_RESPONSE,
    TEST_SET_THING_URL,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_light(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
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

    # Test Light Entity
    entity_id = "light.light_a"
    light_id = "100"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"uniqueid-{light_id}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLights"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(light_id)
    assert data["id"] == light_id
    assert data["state"] == ADVANTAGE_AIR_STATE_ON
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLights"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(light_id)
    assert data["id"] == light_id
    assert data["state"] == ADVANTAGE_AIR_STATE_OFF
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test Dimmable Light Entity
    entity_id = "light.light_b"
    light_id = "101"

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"uniqueid-{light_id}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLights"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(light_id)
    assert data["id"] == light_id
    assert data["state"] == ADVANTAGE_AIR_STATE_ON
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id], ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setLights"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(light_id)
    assert data["id"] == light_id
    assert data["value"] == 50
    assert data["state"] == ADVANTAGE_AIR_STATE_ON
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"


async def test_things_light(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test things lights."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )
    aioclient_mock.get(
        TEST_SET_THING_URL,
        text=TEST_SET_RESPONSE,
    )

    await add_mock_config(hass)

    registry = er.async_get(hass)

    # Test Switch Entity
    entity_id = "light.thing_light_dimmable"
    light_id = "204"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-204"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setThings"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(light_id)
    assert data["id"] == light_id
    assert data["value"] == 0
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id], ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setThings"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(light_id)
    assert data["id"] == light_id
    assert data["value"] == 50
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"
