"""deCONZ number platform tests."""

from unittest.mock import patch

from homeassistant.const import STATE_UNAVAILABLE

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration


async def test_no_number_entities(hass, aioclient_mock):
    """Test that no sensors in deconz results in no number entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of binary sensor entities."""
    data = {
        "sensors": {
            "1": {
                "name": "Presence sensor",
                "type": "ZHAPresence",
                "state": {"dark": False, "presence": False},
                "config": {
                    "duration": 1,
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
    number = hass.states.get("number.presence_sensor_duration")
    assert number.state == "1"

    # event_changed_sensor = {
    #     "t": "event",
    #     "e": "changed",
    #     "r": "sensors",
    #     "id": "1",
    #     "state": {"presence": True},
    # }
    # await mock_deconz_websocket(data=event_changed_sensor)
    # await hass.async_block_till_done()

    # assert hass.states.get("binary_sensor.presence_sensor").state == STATE_ON

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert hass.states.get("number.presence_sensor_duration").state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
