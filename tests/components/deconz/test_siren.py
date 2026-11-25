"""deCONZ switch platform tests."""

from collections.abc import Callable

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SirenService,
    SirenServiceArgument,
)
from homeassistant.const import STATE_OFF, STATE_ON, TargetKey
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType


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
        SirenService.TURN_ON,
        {TargetKey.ENTITY_ID: "siren.warning_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"alert": "lselect"}

    # Service turn off siren

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TURN_OFF,
        {TargetKey.ENTITY_ID: "siren.warning_device"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"alert": "none"}

    # Service turn on siren with duration

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TURN_ON,
        {
            TargetKey.ENTITY_ID: "siren.warning_device",
            SirenServiceArgument.DURATION: 10,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"alert": "lselect", "ontime": 100}
