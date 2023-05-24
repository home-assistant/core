"""Test the Advantage Air Cover Platform."""
from json import loads

from homeassistant.components.advantage_air.const import (
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OPEN,
)
from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    CoverDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OPEN
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


async def test_ac_cover(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test cover platform."""

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

    # Test Cover Zone Entity
    entity_id = "cover.myauto_zone_y"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("device_class") == CoverDeviceClass.DAMPER
    assert state.attributes.get("current_position") == 100

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac3-z01"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["zones"]["z01"]["state"] == ADVANTAGE_AIR_STATE_CLOSE
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["zones"]["z01"]["state"] == ADVANTAGE_AIR_STATE_OPEN
    assert data["ac3"]["zones"]["z01"]["value"] == 100
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 50},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["zones"]["z01"]["value"] == 50
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 0},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[-2][0] == "GET"
    assert aioclient_mock.mock_calls[-2][1].path == "/setAircon"
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["zones"]["z01"]["state"] == ADVANTAGE_AIR_STATE_CLOSE
    assert aioclient_mock.mock_calls[-1][0] == "GET"
    assert aioclient_mock.mock_calls[-1][1].path == "/getSystemData"

    # Test controlling multiple Cover Zone Entity
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {
            ATTR_ENTITY_ID: [
                "cover.myauto_zone_y",
                "cover.myauto_zone_z",
            ]
        },
        blocking=True,
    )
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["zones"]["z01"]["state"] == ADVANTAGE_AIR_STATE_CLOSE
    assert data["ac3"]["zones"]["z02"]["state"] == ADVANTAGE_AIR_STATE_CLOSE
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {
            ATTR_ENTITY_ID: [
                "cover.myauto_zone_y",
                "cover.myauto_zone_z",
            ]
        },
        blocking=True,
    )
    data = loads(aioclient_mock.mock_calls[-2][1].query["json"])
    assert data["ac3"]["zones"]["z01"]["state"] == ADVANTAGE_AIR_STATE_OPEN
    assert data["ac3"]["zones"]["z02"]["state"] == ADVANTAGE_AIR_STATE_OPEN


async def test_things_cover(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test cover platform."""

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

    # Test Blind 1 Entity
    entity_id = "cover.blind_1"
    thing_id = "200"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("device_class") == CoverDeviceClass.BLIND

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-200"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
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
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
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
