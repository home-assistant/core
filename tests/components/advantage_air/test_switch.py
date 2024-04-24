"""Test the Advantage Air Switch Platform."""
from json import loads

from homeassistant.components.advantage_air.const import (
    ADVANTAGE_AIR_STATE_OFF,
    ADVANTAGE_AIR_STATE_ON,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    TEST_SET_RESPONSE,
    TEST_SET_THING_URL,
    TEST_SET_URL,
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_cover_async_setup_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test switch platform."""

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

    # Test Switch Entity
    entity_id = "switch.myzone_fresh_air"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-freshair"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["freshAirStatus"] == ADVANTAGE_AIR_STATE_ON
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac1"]["info"]["freshAirStatus"] == ADVANTAGE_AIR_STATE_OFF
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"


async def test_things_switch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test things switches."""

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
    entity_id = "switch.relay"
    thing_id = "205"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-205"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setThings"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(thing_id)
    assert data["id"] == thing_id
    assert data["value"] == 0
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setThings"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"]).get(thing_id)
    assert data["id"] == thing_id
    assert data["value"] == 100
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"
