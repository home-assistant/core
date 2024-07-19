"""deCONZ switch platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.siren import ATTR_DURATION, DOMAIN as SIREN_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "1": {
                "name": "Warning device",
                "type": "Warning device",
                "state": {"alert": "lselect", "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "name": "Unsupported siren",
                "type": "Not a siren",
                "state": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
        }
    ],
)
async def test_sirens(
    hass: HomeAssistant,
    config_entry_setup: ConfigEntry,
    mock_websocket_data: WebsocketDataType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
) -> None:
    """Test that siren entities are created."""
    assert len(hass.states.async_all()) == 2
    assert hass.states.get("siren.warning_device").state == STATE_ON
    assert not hass.states.get("siren.unsupported_siren")

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"alert": None},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("siren.warning_device").state == STATE_OFF

    # Verify service calls

    aioclient_mock = mock_put_request("/lights/1/state")

    # Service turn on siren

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "siren.warning_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"alert": "lselect"}

    # Service turn off siren

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "siren.warning_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"alert": "none"}

    # Service turn on siren with duration

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "siren.warning_device", ATTR_DURATION: 10},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"alert": "lselect", "ontime": 100}

    await hass.config_entries.async_unload(config_entry_setup.entry_id)

    states = hass.states.async_all()
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
