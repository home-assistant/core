"""deCONZ switch platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.siren import ATTR_DURATION, DOMAIN as SIREN_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "name": "Warning device",
            "type": "Warning device",
            "state": {"alert": "lselect", "reachable": True},
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_sirens(
    hass: HomeAssistant,
    light_ws_data: WebsocketDataType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
) -> None:
    """Test that siren entities are created."""
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("siren.warning_device").state == STATE_ON

    await light_ws_data({"state": {"alert": None}})
    assert hass.states.get("siren.warning_device").state == STATE_OFF

    # Verify service calls

    aioclient_mock = mock_put_request("/lights/0/state")

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
