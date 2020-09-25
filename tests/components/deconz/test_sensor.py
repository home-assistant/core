"""deCONZ sensor platform tests."""
from copy import deepcopy

from homeassistant.components import deconz
from homeassistant.components.deconz.deconz_event import EVENT
import homeassistant.components.sensor as sensor
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
)
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

SENSORS = {
    "1": {
        "id": "Light sensor id",
        "name": "Light level sensor",
        "type": "ZHALightLevel",
        "state": {"lightlevel": 30000, "dark": False},
        "config": {"on": True, "reachable": True, "temperature": 10},
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Presence sensor id",
        "name": "Presence sensor",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "Switch 1 id",
        "name": "Switch 1",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "id": "Switch 2 id",
        "name": "Switch 2",
        "type": "ZHASwitch",
        "state": {"buttonevent": 1000},
        "config": {"battery": 100},
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
    "5": {
        "id": "Daylight sensor id",
        "name": "Daylight sensor",
        "type": "Daylight",
        "state": {"daylight": True, "status": 130},
        "config": {},
        "uniqueid": "00:00:00:00:00:00:00:04-00",
    },
    "6": {
        "id": "Power sensor id",
        "name": "Power sensor",
        "type": "ZHAPower",
        "state": {"current": 2, "power": 6, "voltage": 3},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:05-00",
    },
    "7": {
        "id": "Consumption id",
        "name": "Consumption sensor",
        "type": "ZHAConsumption",
        "state": {"consumption": 2, "power": 6},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:06-00",
    },
    "8": {
        "id": "CLIP light sensor id",
        "name": "CLIP light level sensor",
        "type": "CLIPLightLevel",
        "state": {"lightlevel": 30000},
        "config": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:07-00",
    },
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, sensor.DOMAIN, {"sensor": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_sensors(hass):
    """Test that no sensors in deconz results in no sensor entities."""
    gateway = await setup_deconz_integration(hass)
    assert len(gateway.deconz_ids) == 0
    assert len(hass.states.async_all()) == 0
    assert len(gateway.entities[sensor.DOMAIN]) == 0


async def test_sensors(hass):
    """Test successful creation of sensor entities."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    assert "sensor.light_level_sensor" in gateway.deconz_ids
    assert "sensor.presence_sensor" not in gateway.deconz_ids
    assert "sensor.switch_1" not in gateway.deconz_ids
    assert "sensor.switch_1_battery_level" not in gateway.deconz_ids
    assert "sensor.switch_2" not in gateway.deconz_ids
    assert "sensor.switch_2_battery_level" in gateway.deconz_ids
    assert "sensor.daylight_sensor" not in gateway.deconz_ids
    assert "sensor.power_sensor" in gateway.deconz_ids
    assert "sensor.consumption_sensor" in gateway.deconz_ids
    assert "sensor.clip_light_level_sensor" not in gateway.deconz_ids
    assert len(hass.states.async_all()) == 5
    assert len(gateway.entities[sensor.DOMAIN]) == 5

    light_level_sensor = hass.states.get("sensor.light_level_sensor")
    assert light_level_sensor.state == "999.8"
    assert light_level_sensor.attributes["device_class"] == DEVICE_CLASS_ILLUMINANCE

    presence_sensor = hass.states.get("sensor.presence_sensor")
    assert presence_sensor is None

    switch_1 = hass.states.get("sensor.switch_1")
    assert switch_1 is None

    switch_1_battery_level = hass.states.get("sensor.switch_1_battery_level")
    assert switch_1_battery_level is None

    switch_2 = hass.states.get("sensor.switch_2")
    assert switch_2 is None

    switch_2_battery_level = hass.states.get("sensor.switch_2_battery_level")
    assert switch_2_battery_level.state == "100"
    assert switch_2_battery_level.attributes["device_class"] == DEVICE_CLASS_BATTERY

    daylight_sensor = hass.states.get("sensor.daylight_sensor")
    assert daylight_sensor is None

    power_sensor = hass.states.get("sensor.power_sensor")
    assert power_sensor.state == "6"
    assert power_sensor.attributes["device_class"] == DEVICE_CLASS_POWER

    consumption_sensor = hass.states.get("sensor.consumption_sensor")
    assert consumption_sensor.state == "0.002"
    assert "device_class" not in consumption_sensor.attributes

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"lightlevel": 2000},
    }
    gateway.api.event_handler(state_changed_event)

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "4",
        "config": {"battery": 75},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    light_level_sensor = hass.states.get("sensor.light_level_sensor")
    assert light_level_sensor.state == "1.6"

    switch_2_battery_level = hass.states.get("sensor.switch_2_battery_level")
    assert switch_2_battery_level.state == "75"

    await gateway.async_reset()

    assert len(hass.states.async_all()) == 0
    # Daylight sensor from deCONZ is added to set but is disabled by default
    assert len(gateway.entities[sensor.DOMAIN]) == 1


async def test_allow_clip_sensors(hass):
    """Test that CLIP sensors can be allowed."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = deepcopy(SENSORS)
    gateway = await setup_deconz_integration(
        hass,
        options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: True},
        get_state_response=data,
    )
    assert "sensor.light_level_sensor" in gateway.deconz_ids
    assert "sensor.presence_sensor" not in gateway.deconz_ids
    assert "sensor.switch_1" not in gateway.deconz_ids
    assert "sensor.switch_1_battery_level" not in gateway.deconz_ids
    assert "sensor.switch_2" not in gateway.deconz_ids
    assert "sensor.switch_2_battery_level" in gateway.deconz_ids
    assert "sensor.daylight_sensor" not in gateway.deconz_ids
    assert "sensor.power_sensor" in gateway.deconz_ids
    assert "sensor.consumption_sensor" in gateway.deconz_ids
    assert "sensor.clip_light_level_sensor" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 6
    assert len(gateway.entities[sensor.DOMAIN]) == 6

    light_level_sensor = hass.states.get("sensor.light_level_sensor")
    assert light_level_sensor.state == "999.8"

    presence_sensor = hass.states.get("sensor.presence_sensor")
    assert presence_sensor is None

    switch_1 = hass.states.get("sensor.switch_1")
    assert switch_1 is None

    switch_1_battery_level = hass.states.get("sensor.switch_1_battery_level")
    assert switch_1_battery_level is None

    switch_2 = hass.states.get("sensor.switch_2")
    assert switch_2 is None

    switch_2_battery_level = hass.states.get("sensor.switch_2_battery_level")
    assert switch_2_battery_level.state == "100"

    daylight_sensor = hass.states.get("sensor.daylight_sensor")
    assert daylight_sensor is None

    power_sensor = hass.states.get("sensor.power_sensor")
    assert power_sensor.state == "6"

    consumption_sensor = hass.states.get("sensor.consumption_sensor")
    assert consumption_sensor.state == "0.002"

    clip_light_level_sensor = hass.states.get("sensor.clip_light_level_sensor")
    assert clip_light_level_sensor.state == "999.8"

    hass.config_entries.async_update_entry(
        gateway.config_entry, options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert "sensor.light_level_sensor" in gateway.deconz_ids
    assert "sensor.presence_sensor" not in gateway.deconz_ids
    assert "sensor.switch_1" not in gateway.deconz_ids
    assert "sensor.switch_1_battery_level" not in gateway.deconz_ids
    assert "sensor.switch_2" not in gateway.deconz_ids
    assert "sensor.switch_2_battery_level" in gateway.deconz_ids
    assert "sensor.daylight_sensor" not in gateway.deconz_ids
    assert "sensor.power_sensor" in gateway.deconz_ids
    assert "sensor.consumption_sensor" in gateway.deconz_ids
    assert "sensor.clip_light_level_sensor" not in gateway.deconz_ids
    assert len(hass.states.async_all()) == 5
    assert len(gateway.entities[sensor.DOMAIN]) == 5

    hass.config_entries.async_update_entry(
        gateway.config_entry, options={deconz.gateway.CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert "sensor.light_level_sensor" in gateway.deconz_ids
    assert "sensor.presence_sensor" not in gateway.deconz_ids
    assert "sensor.switch_1" not in gateway.deconz_ids
    assert "sensor.switch_1_battery_level" not in gateway.deconz_ids
    assert "sensor.switch_2" not in gateway.deconz_ids
    assert "sensor.switch_2_battery_level" in gateway.deconz_ids
    assert "sensor.daylight_sensor" not in gateway.deconz_ids
    assert "sensor.power_sensor" in gateway.deconz_ids
    assert "sensor.consumption_sensor" in gateway.deconz_ids
    assert "sensor.clip_light_level_sensor" in gateway.deconz_ids
    assert len(hass.states.async_all()) == 6
    assert len(gateway.entities[sensor.DOMAIN]) == 6


async def test_add_new_sensor(hass):
    """Test that adding a new sensor works."""
    gateway = await setup_deconz_integration(hass)
    assert len(gateway.deconz_ids) == 0

    state_added_event = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": deepcopy(SENSORS["1"]),
    }
    gateway.api.event_handler(state_added_event)
    await hass.async_block_till_done()

    assert "sensor.light_level_sensor" in gateway.deconz_ids

    light_level_sensor = hass.states.get("sensor.light_level_sensor")
    assert light_level_sensor.state == "999.8"


async def test_add_battery_later(hass):
    """Test that a sensor without an initial battery state creates a battery sensor once state exist."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = {"1": deepcopy(SENSORS["3"])}
    gateway = await setup_deconz_integration(hass, get_state_response=data)
    remote = gateway.api.sensors["1"]
    assert len(gateway.deconz_ids) == 0
    assert len(gateway.events) == 1
    assert len(remote._callbacks) == 2
    assert len(gateway.entities[sensor.DOMAIN]) == 0
    assert len(gateway.entities[EVENT]) == 1

    remote.update({"config": {"battery": 50}})
    await hass.async_block_till_done()

    assert len(gateway.deconz_ids) == 1
    assert len(gateway.events) == 1
    assert len(remote._callbacks) == 2

    battery_sensor = hass.states.get("sensor.switch_1_battery_level")
    assert battery_sensor is not None
    assert len(gateway.entities[sensor.DOMAIN]) == 1
    assert len(gateway.entities[EVENT]) == 1
