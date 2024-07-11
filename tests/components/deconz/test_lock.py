"""deCONZ lock platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_LOCKED,
    STATE_UNAVAILABLE,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "1": {
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
        }
    ],
)
async def test_lock_from_light(
    hass: HomeAssistant,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that all supported lock entities based on lights are created."""
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("lock.door_lock").state == STATE_UNLOCKED

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"on": True},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("lock.door_lock").state == STATE_LOCKED

    # Verify service calls

    aioclient_mock = mock_put_request("/lights/1/state")

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

    await hass.config_entries.async_unload(config_entry_setup.entry_id)

    states = hass.states.async_all()
    assert len(states) == 1
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
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
        }
    ],
)
async def test_lock_from_sensor(
    hass: HomeAssistant,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that all supported lock entities based on sensors are created."""
    assert len(hass.states.async_all()) == 2
    assert hass.states.get("lock.door_lock").state == STATE_UNLOCKED

    event_changed_light = {
        "r": "sensors",
        "id": "1",
        "state": {"lockstate": "locked"},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("lock.door_lock").state == STATE_LOCKED

    # Verify service calls

    aioclient_mock = mock_put_request("/sensors/1/config")

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

    await hass.config_entries.async_unload(config_entry_setup.entry_id)

    states = hass.states.async_all()
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
