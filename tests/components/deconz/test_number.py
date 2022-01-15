"""deCONZ number platform tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)


async def test_no_number_entities(hass, aioclient_mock):
    """Test that no sensors in deconz results in no number entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of binary sensor entities."""
    data = {
        "sensors": {
            "0": {
                "name": "Presence sensor",
                "type": "ZHAPresence",
                "state": {"dark": False, "presence": False},
                "config": {
                    "delay": 0,
                    "on": True,
                    "reachable": True,
                    "temperature": 10,
                },
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 3
    assert hass.states.get("number.presence_sensor_delay").state == "0"

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"delay": 10},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("number.presence_sensor_delay").state == "10"

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service set supported value

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.presence_sensor_delay", ATTR_VALUE: 111},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"delay": 111}

    # Service set float value

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.presence_sensor_delay", ATTR_VALUE: 0.1},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"delay": 0}

    # Service set value beyond the supported range

    with pytest.raises(ValueError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.presence_sensor_delay", ATTR_VALUE: 66666},
            blocking=True,
        )

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert hass.states.get("number.presence_sensor_delay").state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
