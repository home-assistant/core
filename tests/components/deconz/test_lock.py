"""deCONZ lock platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "etag": "5c2ec06cde4bd654aef3a555fcd8ad12",
            "hascolor": False,
            "lastannounced": None,
            "lastseen": "2020-08-22T15:29:03Z",
            "manufacturername": "Danalock",
            "modelid": "V3-BTZB",
            "name": "Door lock",
            "state": {"alert": "none", "on": False, "reachable": True},
            "swversion": "19042019",
            "type": "Door Lock",
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_lock_from_light(
    hass: HomeAssistant,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    light_ws_data: WebsocketDataType,
) -> None:
    """Test that all supported lock entities based on lights are created."""
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("lock.door_lock").state == LockState.UNLOCKED

    await light_ws_data({"state": {"on": True}})
    assert hass.states.get("lock.door_lock").state == LockState.LOCKED

    # Verify service calls

    aioclient_mock = mock_put_request("/lights/0/state")

    # Service lock door

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.door_lock"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True}

    # Service unlock door

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.door_lock"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"on": False}


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "config": {
                "battery": 100,
                "lock": False,
                "on": True,
                "reachable": True,
            },
            "ep": 11,
            "etag": "a43862f76b7fa48b0fbb9107df123b0e",
            "lastseen": "2021-03-06T22:25Z",
            "manufacturername": "Onesti Products AS",
            "modelid": "easyCodeTouch_v1",
            "name": "Door lock",
            "state": {
                "lastupdated": "2021-03-06T21:25:45.624",
                "lockstate": "unlocked",
            },
            "swversion": "20201211",
            "type": "ZHADoorLock",
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_lock_from_sensor(
    hass: HomeAssistant,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    sensor_ws_data: WebsocketDataType,
) -> None:
    """Test that all supported lock entities based on sensors are created."""
    assert len(hass.states.async_all()) == 2
    assert hass.states.get("lock.door_lock").state == LockState.UNLOCKED

    await sensor_ws_data({"state": {"lockstate": "locked"}})
    assert hass.states.get("lock.door_lock").state == LockState.LOCKED

    # Verify service calls

    aioclient_mock = mock_put_request("/sensors/0/config")

    # Service lock door

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.door_lock"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"lock": True}

    # Service unlock door

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.door_lock"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"lock": False}
