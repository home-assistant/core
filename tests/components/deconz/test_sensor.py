"""deCONZ sensor platform tests."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.deconz.const import CONF_ALLOW_CLIP_SENSOR
from homeassistant.components.deconz.sensor import ATTR_DAYLIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.common import async_fire_time_changed


async def test_no_sensors(hass, aioclient_mock):
    """Test that no sensors in deconz results in no sensor entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_sensors(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of sensor entities."""
    data = {
        "sensors": {
            "1": {
                "name": "Light level sensor",
                "type": "ZHALightLevel",
                "state": {"daylight": 6955, "lightlevel": 30000, "dark": False},
                "config": {"on": True, "reachable": True, "temperature": 10},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "name": "Presence sensor",
                "type": "ZHAPresence",
                "state": {"presence": False},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "3": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
            "4": {
                "name": "Switch 2",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:03-00",
            },
            "5": {
                "name": "Power sensor",
                "type": "ZHAPower",
                "state": {"current": 2, "power": 6, "voltage": 3},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:05-00",
            },
            "6": {
                "name": "Consumption sensor",
                "type": "ZHAConsumption",
                "state": {"consumption": 2, "power": 6},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:06-00",
            },
            "7": {
                "id": "CLIP light sensor id",
                "name": "CLIP light level sensor",
                "type": "CLIPLightLevel",
                "state": {"lightlevel": 30000},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:07-00",
            },
        }
    }

    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 5

    light_level_sensor = hass.states.get("sensor.light_level_sensor")
    assert light_level_sensor.state == "999.8"
    assert light_level_sensor.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ILLUMINANCE
    assert light_level_sensor.attributes[ATTR_DAYLIGHT] == 6955

    assert not hass.states.get("sensor.presence_sensor")
    assert not hass.states.get("sensor.switch_1")
    assert not hass.states.get("sensor.switch_1_battery_level")
    assert not hass.states.get("sensor.switch_2")

    switch_2_battery_level = hass.states.get("sensor.switch_2_battery_level")
    assert switch_2_battery_level.state == "100"
    assert switch_2_battery_level.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_BATTERY

    assert not hass.states.get("sensor.daylight_sensor")

    power_sensor = hass.states.get("sensor.power_sensor")
    assert power_sensor.state == "6"
    assert power_sensor.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER

    consumption_sensor = hass.states.get("sensor.consumption_sensor")
    assert consumption_sensor.state == "0.002"
    assert ATTR_DEVICE_CLASS not in consumption_sensor.attributes

    assert not hass.states.get("sensor.clip_light_level_sensor")

    # Event signals new light level

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "state": {"lightlevel": 2000},
    }
    await mock_deconz_websocket(data=event_changed_sensor)

    assert hass.states.get("sensor.light_level_sensor").state == "1.6"

    # Event signals new battery level

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "4",
        "config": {"battery": 75},
    }
    await mock_deconz_websocket(data=event_changed_sensor)

    assert hass.states.get("sensor.switch_2_battery_level").state == "75"

    # Unload entry

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 5
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_allow_clip_sensors(hass, aioclient_mock):
    """Test that CLIP sensors can be allowed."""
    data = {
        "sensors": {
            "1": {
                "name": "Light level sensor",
                "type": "ZHALightLevel",
                "state": {"lightlevel": 30000, "dark": False},
                "config": {"on": True, "reachable": True, "temperature": 10},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "id": "CLIP light sensor id",
                "name": "CLIP light level sensor",
                "type": "CLIPLightLevel",
                "state": {"lightlevel": 30000},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(
            hass,
            aioclient_mock,
            options={CONF_ALLOW_CLIP_SENSOR: True},
        )

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("sensor.clip_light_level_sensor").state == "999.8"

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert not hass.states.get("sensor.clip_light_level_sensor")

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("sensor.clip_light_level_sensor").state == "999.8"


async def test_add_new_sensor(hass, aioclient_mock, mock_deconz_websocket):
    """Test that adding a new sensor works."""
    event_added_sensor = {
        "t": "event",
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": {
            "id": "Light sensor id",
            "name": "Light level sensor",
            "type": "ZHALightLevel",
            "state": {"lightlevel": 30000, "dark": False},
            "config": {"on": True, "reachable": True, "temperature": 10},
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
    }

    await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 0

    await mock_deconz_websocket(data=event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("sensor.light_level_sensor").state == "999.8"


async def test_add_battery_later(hass, aioclient_mock, mock_deconz_websocket):
    """Test that a sensor without an initial battery state creates a battery sensor once state exist."""
    data = {
        "sensors": {
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("sensor.switch_1_battery_level")

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"battery": 50},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("sensor.switch_1_battery_level").state == "50"


async def test_special_danfoss_battery_creation(hass, aioclient_mock):
    """Test the special Danfoss battery creation works.

    Normally there should only be one battery sensor per device from deCONZ.
    With specific Danfoss devices each endpoint can report its own battery state.
    """
    data = {
        "sensors": {
            "1": {
                "config": {
                    "battery": 70,
                    "heatsetpoint": 2300,
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                    "schedule": {},
                    "schedule_on": False,
                },
                "ep": 1,
                "etag": "982d9acc38bee5b251e24a9be26558e4",
                "lastseen": "2021-02-15T12:23Z",
                "manufacturername": "Danfoss",
                "modelid": "0x8030",
                "name": "0x8030",
                "state": {
                    "lastupdated": "2021-02-15T12:23:07.994",
                    "on": False,
                    "temperature": 2307,
                },
                "swversion": "YYYYMMDD",
                "type": "ZHAThermostat",
                "uniqueid": "58:8e:81:ff:fe:00:11:22-01-0201",
            },
            "2": {
                "config": {
                    "battery": 86,
                    "heatsetpoint": 2300,
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                    "schedule": {},
                    "schedule_on": False,
                },
                "ep": 2,
                "etag": "62f12749f9f51c950086aff37dd02b61",
                "lastseen": "2021-02-15T12:23Z",
                "manufacturername": "Danfoss",
                "modelid": "0x8030",
                "name": "0x8030",
                "state": {
                    "lastupdated": "2021-02-15T12:23:22.399",
                    "on": False,
                    "temperature": 2316,
                },
                "swversion": "YYYYMMDD",
                "type": "ZHAThermostat",
                "uniqueid": "58:8e:81:ff:fe:00:11:22-02-0201",
            },
            "3": {
                "config": {
                    "battery": 86,
                    "heatsetpoint": 2350,
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                    "schedule": {},
                    "schedule_on": False,
                },
                "ep": 3,
                "etag": "f50061174bb7f18a3d95789bab8b646d",
                "lastseen": "2021-02-15T12:23Z",
                "manufacturername": "Danfoss",
                "modelid": "0x8030",
                "name": "0x8030",
                "state": {
                    "lastupdated": "2021-02-15T12:23:25.466",
                    "on": False,
                    "temperature": 2337,
                },
                "swversion": "YYYYMMDD",
                "type": "ZHAThermostat",
                "uniqueid": "58:8e:81:ff:fe:00:11:22-03-0201",
            },
            "4": {
                "config": {
                    "battery": 85,
                    "heatsetpoint": 2300,
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                    "schedule": {},
                    "schedule_on": False,
                },
                "ep": 4,
                "etag": "eea97adf8ce1b971b8b6a3a31793f96b",
                "lastseen": "2021-02-15T12:23Z",
                "manufacturername": "Danfoss",
                "modelid": "0x8030",
                "name": "0x8030",
                "state": {
                    "lastupdated": "2021-02-15T12:23:41.939",
                    "on": False,
                    "temperature": 2333,
                },
                "swversion": "YYYYMMDD",
                "type": "ZHAThermostat",
                "uniqueid": "58:8e:81:ff:fe:00:11:22-04-0201",
            },
            "5": {
                "config": {
                    "battery": 83,
                    "heatsetpoint": 2300,
                    "offset": 0,
                    "on": True,
                    "reachable": True,
                    "schedule": {},
                    "schedule_on": False,
                },
                "ep": 5,
                "etag": "1f7cd1a5d66dc27ac5eb44b8c47362fb",
                "lastseen": "2021-02-15T12:23Z",
                "manufacturername": "Danfoss",
                "modelid": "0x8030",
                "name": "0x8030",
                "state": {"lastupdated": "none", "on": False, "temperature": 2325},
                "swversion": "YYYYMMDD",
                "type": "ZHAThermostat",
                "uniqueid": "58:8e:81:ff:fe:00:11:22-05-0201",
            },
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 10
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 5


async def test_air_quality_sensor(hass, aioclient_mock):
    """Test successful creation of air quality sensor entities."""
    data = {
        "sensors": {
            "0": {
                "config": {"on": True, "reachable": True},
                "ep": 2,
                "etag": "c2d2e42396f7c78e11e46c66e2ec0200",
                "lastseen": "2020-11-20T22:48Z",
                "manufacturername": "BOSCH",
                "modelid": "AIR",
                "name": "Air quality",
                "state": {
                    "airquality": "poor",
                    "airqualityppb": 809,
                    "lastupdated": "2020-11-20T22:48:00.209",
                },
                "swversion": "20200402",
                "type": "ZHAAirQuality",
                "uniqueid": "00:12:4b:00:14:4d:00:07-02-fdef",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("sensor.air_quality").state == "poor"


async def test_daylight_sensor(hass, aioclient_mock):
    """Test daylight sensor is disabled by default and when created has expected attributes."""
    data = {
        "sensors": {
            "0": {
                "config": {
                    "configured": True,
                    "on": True,
                    "sunriseoffset": 30,
                    "sunsetoffset": -30,
                },
                "etag": "55047cf652a7e594d0ee7e6fae01dd38",
                "manufacturername": "Philips",
                "modelid": "PHDL00",
                "name": "Daylight sensor",
                "state": {
                    "daylight": True,
                    "lastupdated": "2018-03-24T17:26:12",
                    "status": 170,
                },
                "swversion": "1.0",
                "type": "Daylight",
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 0
    assert not hass.states.get("sensor.daylight_sensor")

    # Enable in entity registry

    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(
        entity_id="sensor.daylight_sensor", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("sensor.daylight_sensor")
    assert hass.states.get("sensor.daylight_sensor").attributes[ATTR_DAYLIGHT]


async def test_time_sensor(hass, aioclient_mock):
    """Test successful creation of time sensor entities."""
    data = {
        "sensors": {
            "0": {
                "config": {"battery": 40, "on": True, "reachable": True},
                "ep": 1,
                "etag": "28e796678d9a24712feef59294343bb6",
                "lastseen": "2020-11-22T11:26Z",
                "manufacturername": "Danfoss",
                "modelid": "eTRV0100",
                "name": "Time",
                "state": {
                    "lastset": "2020-11-19T08:07:08Z",
                    "lastupdated": "2020-11-22T10:51:03.444",
                    "localtime": "2020-11-22T10:51:01",
                    "utc": "2020-11-22T10:51:01Z",
                },
                "swversion": "20200429",
                "type": "ZHATime",
                "uniqueid": "cc:cc:cc:ff:fe:38:4d:b3-01-000a",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("sensor.time").state == "2020-11-19T08:07:08Z"
    assert hass.states.get("sensor.time_battery_level").state == "40"


async def test_unsupported_sensor(hass, aioclient_mock):
    """Test that unsupported sensors doesn't break anything."""
    data = {
        "sensors": {
            "0": {"type": "not supported", "name": "name", "state": {}, "config": {}}
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("sensor.name").state == STATE_UNKNOWN
