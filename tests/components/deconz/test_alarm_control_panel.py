"""deCONZ alarm control panel platform tests."""

from unittest.mock import patch

from homeassistant.const import STATE_UNAVAILABLE

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration


async def test_no_sensors(hass, aioclient_mock):
    """Test that no sensors in deconz results in no climate entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_alarm_control_panel(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of alarm control panel entities."""
    data = {
        "sensors": {
            "0": {
                "config": {
                    "armed": "disarmed",
                    "enrolled": 0,
                    "on": True,
                    "pending": [],
                    "reachable": True,
                },
                "ep": 1,
                "etag": "3c4008d74035dfaa1f0bb30d24468b12",
                "lastseen": "2021-04-02T13:07Z",
                "manufacturername": "Universal Electronics Inc",
                "modelid": "URC4450BC0-X-R",
                "name": "Keypad",
                "state": {
                    "action": "armed_away,1111,55",
                    "lastupdated": "2021-04-02T13:08:18.937",
                    "lowbattery": False,
                    "panel": "disarmed",
                    "tampered": True,
                },
                "type": "ZHAAncillaryControlSensor",
                "uniqueid": "00:0d:6f:00:13:4f:61:39-01-0501",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("alarm_control_panel.keypad")

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 1
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
