"""Test deCONZ remote events."""
from copy import deepcopy

from homeassistant.components.deconz.deconz_event import CONF_DECONZ_EVENT

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.common import async_capture_events

SENSORS = {
    "1": {
        "id": "Switch 1 id",
        "name": "Switch 1",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "2": {
        "id": "Switch 2 id",
        "name": "Switch 2",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {"battery": 100},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "3": {
        "id": "Switch 3 id",
        "name": "Switch 3",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000, "gesture": 1},
        "config": {"battery": 100},
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
    "4": {
        "id": "Switch 4 id",
        "name": "Switch 4",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000, "gesture": 1},
        "config": {"battery": 100},
        "uniqueid": "00:00:00:00:00:00:00:04-00",
    },
}


async def test_deconz_events(hass):
    """Test successful creation of deconz events."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    assert "sensor.switch_1" not in gateway.deconz_ids
    assert "sensor.switch_1_battery_level" not in gateway.deconz_ids
    assert "sensor.switch_2" not in gateway.deconz_ids
    assert "sensor.switch_2_battery_level" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 3
    assert len(gateway.events) == 4

    switch_1 = hass.states.get("sensor.switch_1")
    assert switch_1 is None

    switch_1_battery_level = hass.states.get("sensor.switch_1_battery_level")
    assert switch_1_battery_level is None

    switch_2 = hass.states.get("sensor.switch_2")
    assert switch_2 is None

    switch_2_battery_level = hass.states.get("sensor.switch_2_battery_level")
    assert switch_2_battery_level.state == "100"

    events = async_capture_events(hass, CONF_DECONZ_EVENT)

    gateway.api.sensors["1"].update({"state": {"buttonevent": 2000}})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        "id": "switch_1",
        "unique_id": "00:00:00:00:00:00:00:01",
        "event": 2000,
    }

    gateway.api.sensors["3"].update({"state": {"buttonevent": 2000}})
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[1].data == {
        "id": "switch_3",
        "unique_id": "00:00:00:00:00:00:00:03",
        "event": 2000,
        "gesture": 1,
    }

    gateway.api.sensors["4"].update({"state": {"gesture": 0}})
    await hass.async_block_till_done()

    assert len(events) == 3
    assert events[2].data == {
        "id": "switch_4",
        "unique_id": "00:00:00:00:00:00:00:04",
        "event": 1000,
        "gesture": 0,
    }

    await gateway.async_reset()

    assert len(hass.states.async_all()) == 0
    assert len(gateway.events) == 0
