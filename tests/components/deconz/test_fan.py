"""deCONZ fan platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "1": {
                "etag": "432f3de28965052961a99e3c5494daf4",
                "hascolor": False,
                "manufacturername": "King Of Fans,  Inc.",
                "modelid": "HDC52EastwindFan",
                "name": "Ceiling fan",
                "state": {
                    "alert": "none",
                    "bri": 254,
                    "on": False,
                    "reachable": True,
                    "speed": 4,
                },
                "swversion": "0000000F",
                "type": "Fan",
                "uniqueid": "00:22:a3:00:00:27:8b:81-01",
            }
        }
    ],
)
async def test_fans(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that all supported fan entities are created."""
    assert len(hass.states.async_all()) == 2  # Light and fan
    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE] == 100

    # Test states

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"speed": 1},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE] == 25

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"speed": 2},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE] == 50

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"speed": 3},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE] == 75

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"speed": 4},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE] == 100

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"speed": 0},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_OFF
    assert hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE] == 0

    # Test service calls

    aioclient_mock = mock_put_request("/lights/1/state")

    # Service turn on fan using saved default_on_speed

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.ceiling_fan"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"speed": 4}

    # Service turn off fan

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.ceiling_fan"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"speed": 0}

    # Service turn on fan to 20%

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.ceiling_fan", ATTR_PERCENTAGE: 20},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"speed": 1}

    # Service set fan percentage to 20%

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.ceiling_fan", ATTR_PERCENTAGE: 20},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"speed": 1}

    # Service set fan percentage to 40%

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.ceiling_fan", ATTR_PERCENTAGE: 40},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[5][2] == {"speed": 2}

    # Service set fan percentage to 60%

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.ceiling_fan", ATTR_PERCENTAGE: 60},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[6][2] == {"speed": 3}

    # Service set fan percentage to 80%

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.ceiling_fan", ATTR_PERCENTAGE: 80},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[7][2] == {"speed": 4}

    # Service set fan percentage to 0% does not equal off

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.ceiling_fan", ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[8][2] == {"speed": 0}

    # Events with an unsupported speed does not get converted

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"speed": 5},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert not hass.states.get("fan.ceiling_fan").attributes[ATTR_PERCENTAGE]

    await hass.config_entries.async_unload(config_entry_setup.entry_id)

    states = hass.states.async_all()
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
