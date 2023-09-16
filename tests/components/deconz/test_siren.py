"""deCONZ switch platform tests."""
from unittest.mock import patch

from homeassistant.components.siren import ATTR_DURATION, DOMAIN as SIREN_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sirens(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_deconz_websocket
) -> None:
    """Test that siren entities are created."""
    data = {
        "lights": {
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
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("siren.warning_device").state == STATE_ON
    assert not hass.states.get("siren.unsupported_siren")

    event_changed_light = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"alert": None},
    }
    await mock_deconz_websocket(data=event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("siren.warning_device").state == STATE_OFF

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/1/state")

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

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
