"""Test deCONZ remote events."""

from copy import deepcopy

from homeassistant.components.deconz.deconz_event import CONF_DECONZ_EVENT
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.const import STATE_UNAVAILABLE

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
    "5": {
        "id": "ZHA remote 1 id",
        "name": "ZHA remote 1",
        "type": "ZHASwitch",
        "state": {"angle": 0, "buttonevent": 1000, "xy": [0.0, 0.0]},
        "config": {"group": "4,5,6", "reachable": True, "on": True},
        "uniqueid": "00:00:00:00:00:00:00:05-00",
    },
}


async def test_deconz_events(hass):
    """Test successful creation of deconz events."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 3
    assert len(gateway.events) == 5
    assert hass.states.get("sensor.switch_1") is None
    assert hass.states.get("sensor.switch_1_battery_level") is None
    assert hass.states.get("sensor.switch_2") is None
    assert hass.states.get("sensor.switch_2_battery_level").state == "100"

    events = async_capture_events(hass, CONF_DECONZ_EVENT)

    gateway.api.sensors["1"].update({"state": {"buttonevent": 2000}})
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        "id": "switch_1",
        "unique_id": "00:00:00:00:00:00:00:01",
        "event": 2000,
        "device_id": gateway.events[0].device_id,
    }

    gateway.api.sensors["3"].update({"state": {"buttonevent": 2000}})
    await hass.async_block_till_done()

    assert len(events) == 2
    assert events[1].data == {
        "id": "switch_3",
        "unique_id": "00:00:00:00:00:00:00:03",
        "event": 2000,
        "gesture": 1,
        "device_id": gateway.events[2].device_id,
    }

    gateway.api.sensors["4"].update({"state": {"gesture": 0}})
    await hass.async_block_till_done()

    assert len(events) == 3
    assert events[2].data == {
        "id": "switch_4",
        "unique_id": "00:00:00:00:00:00:00:04",
        "event": 1000,
        "gesture": 0,
        "device_id": gateway.events[3].device_id,
    }

    gateway.api.sensors["5"].update(
        {"state": {"buttonevent": 6002, "angle": 110, "xy": [0.5982, 0.3897]}}
    )
    await hass.async_block_till_done()

    assert len(events) == 4
    assert events[3].data == {
        "id": "zha_remote_1",
        "unique_id": "00:00:00:00:00:00:00:05",
        "event": 6002,
        "angle": 110,
        "xy": [0.5982, 0.3897],
        "device_id": gateway.events[4].device_id,
    }

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(hass.states.async_all()) == 3
    for state in states:
        assert state.state == STATE_UNAVAILABLE
    assert len(gateway.events) == 0

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    assert len(gateway.events) == 0
